#!/usr/bin/env python3
"""Polls a product page and sends a macOS notification when it comes back in stock.

Meant to be triggered every 10 minutes by launchd. It only actually fetches the
product page once per `check_interval_minutes` (default 60) — the other wakeups
are no-ops so the site isn't hit too often while still keeping the check on a
short, reliable heartbeat.
"""

import gzip
import json
import re
import subprocess
import sys
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "state.json"
LOG_PATH = BASE_DIR / "stock_checker.log"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LOG_PATH.open("a") as f:
        f.write(f"[{timestamp}] {message}\n")


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def fetch_page(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
        encoding = response.headers.get("Content-Encoding", "")

    if encoding == "gzip":
        raw = gzip.decompress(raw)
    elif encoding == "deflate":
        raw = zlib.decompress(raw)

    return raw.decode("utf-8", errors="ignore")


def strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).lower()


def determine_status(page_text: str, config: dict) -> str:
    out_phrases = [p.lower() for p in config.get("out_of_stock_phrases", [])]
    in_phrases = [p.lower() for p in config.get("in_stock_phrases", [])]

    if any(phrase in page_text for phrase in out_phrases):
        return "OUT"
    if in_phrases:
        return "IN" if any(phrase in page_text for phrase in in_phrases) else "UNKNOWN"
    return "IN"


def escape_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def send_alert(title: str, message: str) -> None:
    # display dialog (unlike display notification) is a modal window that
    # stays on screen until the user clicks OK, rather than auto-dismissing.
    script = (
        f'display dialog "{escape_applescript(message)}" '
        f'with title "{escape_applescript(title)}" '
        f'buttons {{"OK"}} default button "OK"'
    )
    result = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"osascript alert failed (exit {result.returncode}) for {message!r}: {result.stderr.strip()}")


def fetch_and_classify(entry: dict, attempts: int = 2) -> str:
    """Fetch a URL and classify it, retrying once if the result is UNKNOWN.

    Large sites sometimes return a stripped-down bot-check/redirect page
    instead of the real one; a second attempt often gets the real page.
    Network errors are not retried here — they propagate to the caller.
    """
    status = "UNKNOWN"
    for attempt in range(attempts):
        html = fetch_page(entry["url"])
        status = determine_status(strip_html(html), entry)
        if status != "UNKNOWN":
            return status
    return status


def get_url_entries(config: dict) -> list:
    """Return a list of {"url", "out_of_stock_phrases", "in_stock_phrases"} dicts.

    Each entry in config["urls"] can be a plain URL string (uses the
    top-level phrase lists as defaults) or an object like
    {"url": "...", "out_of_stock_phrases": [...], "in_stock_phrases": [...]}
    to override the phrases for just that URL.
    """
    raw_urls = config.get("urls")
    if not raw_urls:
        legacy_url = config.get("url")  # older configs used a single "url" key
        raw_urls = [legacy_url] if legacy_url else []

    default_out = config.get("out_of_stock_phrases", [])
    default_in = config.get("in_stock_phrases", [])

    entries = []
    for raw in raw_urls:
        if isinstance(raw, dict):
            entries.append({
                "url": raw.get("url"),
                "out_of_stock_phrases": raw.get("out_of_stock_phrases", default_out),
                "in_stock_phrases": raw.get("in_stock_phrases", default_in),
            })
        else:
            entries.append({
                "url": raw,
                "out_of_stock_phrases": default_out,
                "in_stock_phrases": default_in,
            })
    return [e for e in entries if e["url"]]


def main() -> None:
    args = sys.argv[1:]
    test_mode = "--test" in args
    url_filter = next((a for a in args if a != "--test"), None)

    config = load_json(CONFIG_PATH, None)
    entries = get_url_entries(config) if config else []
    if not config or not entries or any("example.com" in e["url"] for e in entries):
        message = "Config missing or still has placeholder URL(s) — run setup.py first."
        log(message)
        if test_mode:
            print(message)
        sys.exit(0)

    if url_filter:
        matched = [e for e in entries if url_filter.lower() in e["url"].lower()]
        if not matched:
            print(f"No configured URL contains '{url_filter}'.")
            sys.exit(1)
        entries = matched

    interval_minutes = config.get("check_interval_minutes", 60)
    state = load_json(STATE_PATH, {"last_check": None, "urls": {}})
    url_states = state.setdefault("urls", {})

    now = datetime.now(timezone.utc)
    if not test_mode and state.get("last_check"):
        last_check = datetime.fromisoformat(state["last_check"])
        elapsed_minutes = (now - last_check).total_seconds() / 60
        if elapsed_minutes < interval_minutes:
            return  # not time for the real check yet, stay quiet

    alerts_to_send = []  # (title, url) — fired only after state is saved, see below

    for entry in entries:
        url = entry["url"]
        url_state = url_states.setdefault(url, {"last_status": None, "last_notified_status": None})

        try:
            status = fetch_and_classify(entry)
        except Exception as exc:  # network errors, timeouts, etc.
            log(f"Fetch failed for {url}: {exc}")
            if test_mode:
                print(f"{url} -> Fetch failed: {exc}")
            continue

        log(f"Checked {url} -> {status}")
        if test_mode:
            print(f"{url} -> {status}")

        if status == "UNKNOWN":
            log(f"Could not determine stock status for {url} — check in_stock_phrases/out_of_stock_phrases in config.json.")
        else:
            previously_notified = url_state.get("last_notified_status")
            is_first_check = previously_notified is None
            if test_mode or (not is_first_check and status != previously_notified):
                title = "Back in stock!" if status == "IN" else "Out of stock"
                alerts_to_send.append((title, url))
            url_state["last_notified_status"] = status  # record baseline even when not alerting

        url_state["last_status"] = status

    state["last_check"] = now.isoformat()
    save_state(state)  # save before any blocking alert dialogs so a stacked launchd run doesn't repeat

    for title, url in alerts_to_send:
        send_alert(title, url)


if __name__ == "__main__":
    main()
