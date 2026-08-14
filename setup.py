#!/usr/bin/env python3
"""Run this manually in Terminal to set (or change) the product URL(s) being monitored."""

import json
from pathlib import Path

from stock_checker import fetch_page

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def check_url(url: str) -> None:
    try:
        fetch_page(url)
    except Exception as exc:  # network errors, 403s, timeouts, etc.
        print(f"  Could not fetch this URL: {exc}")


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
        check_url(url)
        urls.append(url)

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
