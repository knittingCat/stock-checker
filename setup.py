#!/usr/bin/env python3
"""Run this manually in Terminal to set (or change) the product URL(s) being monitored."""

import json
from pathlib import Path

from stock_checker import fetch_page, strip_html

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

# Candidate phrases to scan for automatically. Only ones that actually
# appear on the page (matching what you say the real status is) get used —
# this avoids hand-guessing which exact wording a given site uses.
CANDIDATE_OUT_PHRASES = [
    "out of stock",
    "sold out",
    "currently unavailable",
    "unavailable",
    "temporarily out of stock",
    "temporarily unavailable",
    "not available",
    "notify me when available",
    "email me when available",
    "back order",
    "backordered",
    "no longer available",
]

CANDIDATE_IN_PHRASES = [
    "add to cart",
    "add to bag",
    "add to basket",
    "buy now",
    "buy it now",
    "in stock",
    "ships today",
    "available now",
]


def fetch_url_text(url: str):
    try:
        html = fetch_page(url)
    except Exception as exc:  # network errors, 403s, timeouts, etc.
        print(f"  Could not fetch this URL: {exc}")
        return None
    return strip_html(html)


def discover_phrases(url: str) -> dict:
    """Ask the user the real current status, scan the page for matching
    candidate phrases, and return a per-URL override dict (or a plain
    string entry if the user skips or nothing useful was found)."""
    text = fetch_url_text(url)
    if text is None:
        return {"url": url}

    answer = input("  Is this currently in stock or out of stock? [in/out/skip]: ").strip().lower()
    if answer not in ("in", "out"):
        return {"url": url}

    out_matches = [p for p in CANDIDATE_OUT_PHRASES if p in text]
    in_matches = [p for p in CANDIDATE_IN_PHRASES if p in text]

    entry = {"url": url}

    if answer == "out":
        if out_matches:
            entry["out_of_stock_phrases"] = out_matches
            print(f"  Found out-of-stock phrase(s): {', '.join(out_matches)}")
        else:
            print("  Couldn't find a recognizable out-of-stock phrase on this page.")
        if in_matches:
            print(f"  Note: also found {', '.join(in_matches)} on this page even though it's out of "
                  f"stock — not using {'that' if len(in_matches) == 1 else 'these'} as an in-stock signal.")
    else:  # answer == "in"
        if in_matches:
            entry["in_stock_phrases"] = in_matches
            print(f"  Found in-stock phrase(s): {', '.join(in_matches)}")
        else:
            print("  Couldn't find a recognizable in-stock phrase on this page.")
        if out_matches:
            print(f"  Warning: also found {', '.join(out_matches)} on this page even though it's in "
                  f"stock — excluding {'it' if len(out_matches) == 1 else 'them'} from this URL's "
                  f"out-of-stock phrases to avoid false alerts.")
            entry["out_of_stock_phrases"] = [p for p in CANDIDATE_OUT_PHRASES if p not in out_matches and p in text]

    return entry


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    config.setdefault("out_of_stock_phrases", ["out of stock", "sold out", "unavailable"])
    config.setdefault("check_interval_minutes", 60)

    urls = []
    print("Enter product page URLs to monitor, one per line.")
    print("Press Enter on a blank line when you're done.\n")

    while True:
        label = f"URL #{len(urls) + 1}" if urls else "URL #1 (required)"
        url = input(f"{label}: ").strip()
        if not url:
            if urls:
                break
            print("You need to enter at least one URL.")
            continue

        entry = discover_phrases(url)
        # collapse to a plain string if no overrides were actually found
        urls.append(entry["url"] if set(entry) == {"url"} else entry)

    config["urls"] = urls
    config.pop("url", None)  # replaced by the "urls" list

    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")

    state_path = CONFIG_PATH.parent / "state.json"
    if state_path.exists():
        state_path.unlink()  # forget any previous products' status/notify state

    plural = "URL" if len(urls) == 1 else "URLs"
    print(f"\nSaved. Now monitoring {len(urls)} {plural}.")


if __name__ == "__main__":
    main()
