#!/usr/bin/env python3
"""Run this manually in Terminal to set (or change) the product URL being monitored."""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}

    url = input("Enter the product page URL to monitor: ").strip()
    while not url:
        url = input("URL can't be empty. Enter the product page URL to monitor: ").strip()

    config["url"] = url
    config.setdefault("out_of_stock_phrases", ["out of stock", "sold out", "unavailable"])
    config.setdefault("check_interval_minutes", 60)

    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")

    state_path = CONFIG_PATH.parent / "state.json"
    if state_path.exists():
        state_path.unlink()  # forget any previous product's status/notify state

    print(f"Saved. Now monitoring: {url}")


if __name__ == "__main__":
    main()
