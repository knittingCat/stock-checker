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

Check whether you already have it:

```bash
python3 --version
```

If that prints `command not found`, install Python 3 from
[python.org/downloads](https://www.python.org/downloads/) (download the
macOS installer and run it), then reopen Terminal and try again.

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

```bash
python3 -c "import json,pathlib; p=pathlib.Path('config.json'); c=json.loads(p.read_text()); c['check_interval_minutes']=10; p.write_text(json.dumps(c, indent=2)+'\n')"
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

Open `config.json` in a text editor:

```bash
open -e config.json
```

(this opens it in TextEdit — use `open -a "Visual Studio Code" config.json`
or your editor of choice instead if you prefer). Edit the
`out_of_stock_phrases` list to match the language a specific site uses, save,
and close the editor:

```json
{
  "url": "https://example.com/product",
  "out_of_stock_phrases": ["out of stock", "sold out", "unavailable"],
  "check_interval_minutes": 60
}
```

By default, if none of the `out_of_stock_phrases` are found on the page, the
product is considered in stock. You can optionally add an `in_stock_phrases`
list too — if present, a page is only considered in stock when one of these
phrases is actually found (useful for sites that don't have a clear
"unavailable"-style label but do have a reliable "Add to Cart" button or
similar):

```json
{
  "url": "https://example.com/product",
  "out_of_stock_phrases": ["out of stock", "sold out", "unavailable"],
  "in_stock_phrases": ["add to cart", "add to bag", "buy now"],
  "check_interval_minutes": 60
}
```

If `in_stock_phrases` is set and neither list matches, the status is
`UNKNOWN` — it's logged, but no notification is sent (avoids false alarms).

## Files

- `stock_checker.py` — the checker itself
- `setup.py` — interactive one-time (or repeatable) setup for the URL
- `install.sh` / `uninstall.sh` — manage the background `launchd` job
- `com.stockchecker.plist.template` — launchd job template used by `install.sh`
