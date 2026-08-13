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
    subprocess.run(["osascript", "-e", script], check=False)


def main() -> None:
    test_mode = "--test" in sys.argv

    config = load_json(CONFIG_PATH, None)
    if not config or not config.get("url") or "example.com" in config["url"]:
        message = "Config missing or still has placeholder URL — run setup.py first."
        log(message)
        if test_mode:
            print(message)
        sys.exit(0)

    interval_minutes = config.get("check_interval_minutes", 60)
    state = load_json(STATE_PATH, {"last_check": None, "last_status": None, "last_notified_status": None})

    now = datetime.now(timezone.utc)
    if not test_mode and state.get("last_check"):
        last_check = datetime.fromisoformat(state["last_check"])
        elapsed_minutes = (now - last_check).total_seconds() / 60
        if elapsed_minutes < interval_minutes:
            return  # not time for the real check yet, stay quiet

    try:
        html = fetch_page(config["url"])
    except Exception as exc:  # network errors, timeouts, etc.
        log(f"Fetch failed: {exc}")
        if test_mode:
            print(f"Fetch failed: {exc}")
        state["last_check"] = now.isoformat()
        save_state(state)
        return

    page_text = strip_html(html)
    status = determine_status(page_text, config)
    log(f"Checked {config['url']} -> {status}")
    if test_mode:
        print(f"{config['url']} -> {status}")

    previously_notified = state.get("last_notified_status")
    should_alert = status != "UNKNOWN" and (test_mode or status != previously_notified)

    if status == "UNKNOWN":
        log("Could not determine stock status from page text — check in_stock_phrases/out_of_stock_phrases in config.json.")
    elif should_alert:
        state["last_notified_status"] = status

    state["last_check"] = now.isoformat()
    state["last_status"] = status
    save_state(state)  # save before the blocking alert dialog so a stacked launchd run doesn't repeat

    if should_alert:
        title = "Back in stock!" if status == "IN" else "Out of stock"
        send_alert(title, config["url"])


if __name__ == "__main__":
    main()
