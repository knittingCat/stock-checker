# stock-checker

Watches a product page and fires a native macOS desktop notification when it
comes back in stock (or goes out of stock).

It works on any site: it fetches the page's HTML and looks for common
out-of-stock phrases ("out of stock", "sold out", "unavailable", ...). If
none of those phrases are present, the page is considered in stock. Matching
is case-insensitive.

## Requirements

- macOS (uses `launchd` and `osascript` for notifications)
- Python 3 (no extra packages required — stdlib only)

## Setup

```bash
git clone https://github.com/knittingCat/stock-checker.git
cd stock-checker
python3 setup.py
```

`setup.py` will prompt you for the product URL to monitor and save it to a
local `config.json` (gitignored, so your URL/config never gets committed).

## Run it in the background

```bash
./install.sh
```

This registers a `launchd` agent that wakes up every 10 minutes. By default
it only actually re-fetches the page once an hour (`check_interval_minutes`
in `config.json`) to avoid hammering the site — lower that value if you want
tighter polling, e.g. every 10 minutes:

```json
{
  "check_interval_minutes": 10
}
```

To stop the background job:

```bash
./uninstall.sh
```

## Test it manually

Force an immediate check (bypasses the throttle) and print the result:

```bash
python3 stock_checker.py --test
```

This also always fires a notification regardless of prior state, which is
useful for confirming notifications are working end to end.

## Notifications

Notifications are sent once per state transition — when the page flips from
out-of-stock to in-stock, or back again — not on every single check. If
macOS notifications don't seem to be appearing, check System Settings →
Notifications and make sure Terminal (or whatever app runs the script) is
allowed to notify.

## Customizing detection

Edit the `out_of_stock_phrases` list in `config.json` to match the language
a specific site uses:

```json
{
  "url": "https://example.com/product",
  "out_of_stock_phrases": ["out of stock", "sold out", "unavailable"],
  "check_interval_minutes": 60
}
```

## Files

- `stock_checker.py` — the checker itself
- `setup.py` — interactive one-time (or repeatable) setup for the URL
- `install.sh` / `uninstall.sh` — manage the background `launchd` job
- `com.stockchecker.plist.template` — launchd job template used by `install.sh`
