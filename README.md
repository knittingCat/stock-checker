# Stock-Checker

Watches a product page and fires a native macOS desktop notification when it
comes back in stock (or goes out of stock).

It fetches the page's HTML and looks for common out-of-stock phrases ("out
of stock", "sold out", "unavailable", ...). If none of those phrases are
present, the page is considered in stock. Matching is case-insensitive.

This is a plain HTTP request, not a real browser, so it won't work on every
site. Some retailers (especially large ones) run bot-detection/WAF systems
that block this kind of request outright, regardless of what headers are
sent. If that happens, `stock_checker.py --test` will print and log
something like:

```
Fetch failed: HTTP Error 403: Forbidden
```

A 403 means the site actively refused the request — there's no config
change here that fixes it. Try a different site, or check less-guarded
smaller/niche retailers, which are much more likely to work.

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

`setup.py` will prompt you for one or more product URLs to monitor (enter
them one at a time, blank line when done) and save them to a local
`config.json` (gitignored, so your URLs/config never get committed). As you
enter each URL, it immediately tries fetching it and prints an error message
if that fails (e.g. a 403 error if the site blocks the request — see the
note near the top of this README about what that means).

## Run it in the background

```bash
./install.sh
```

This registers a `launchd` agent that wakes up every 10 minutes. By default
it only actually re-fetches the page once an hour (`check_interval_minutes`
in `config.json`) to avoid hammering the site — lower that value if you want
tighter polling, e.g. every 10 minutes. Open `config.json` in a text editor:

```bash
open -e config.json
```

and change `"check_interval_minutes": 60` to `"check_interval_minutes": 10`
(or whatever value you want), then save and close the editor.

To stop the background job:

```bash
./uninstall.sh
```

### What happens while your Mac is asleep?

`launchd` jobs don't run while the Mac is asleep — the 10-minute timer pauses
along with everything else, so no checks (and no alerts) happen during that
time. When the Mac wakes up, it doesn't try to catch up on every missed
interval; it just resumes based on wall-clock time, and since more than 10
minutes have elapsed, it fires again almost immediately after wake, then
continues on the normal cadence from there. No action is needed from you.

One caveat: if the product went in stock and back out again entirely during
a sleep window (e.g. overnight), that change will be missed — it only knows
what the page looks like at the moment it actually checks.

## Test it manually

Make sure you're in the `stock-checker` directory first (otherwise Python
won't find the file):

```bash
cd ~/stock-checker
```

Then force an immediate check (bypasses the throttle) and print the result:

```bash
python3 stock_checker.py --test
```

This also always fires a notification regardless of prior state, which is
useful for confirming notifications are working end to end.

If you're monitoring more than one URL, add part of the URL you want to
test to only check that one instead of all of them:

```bash
python3 stock_checker.py --test mechanicalgifs
```

This matches against any configured URL containing that text
(case-insensitive). If nothing matches, it tells you and exits instead of
silently checking everything.

## Notifications

Notifications are sent once per state transition — when the page flips from
out-of-stock to in-stock, or back again — not on every single check. The
very first check of a newly-added URL never alerts by itself; it just
records that page's current status as the baseline, so you don't get an
alert immediately after running `setup.py` just because a URL had never
been checked before. If macOS notifications don't seem to be appearing,
check System Settings → Notifications and make sure Terminal (or whatever
app runs the script) is allowed to notify.

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
  "urls": ["https://example.com/product"],
  "out_of_stock_phrases": ["out of stock", "sold out", "unavailable"],
  "check_interval_minutes": 60
}
```

Re-run `python3 setup.py` any time to change which URLs are monitored —
it overwrites the `urls` list and clears old notification state. You can
list as many product URLs as you want; each one gets its own independent
in-stock/out-of-stock tracking and alerts. The same phrase lists apply to
every URL in `urls`. By default, if none of
the `out_of_stock_phrases` are found on a page, that product is considered
in stock. You can optionally add an `in_stock_phrases` list too — if
present, a page is only considered in stock when one of these phrases is
actually found (useful for sites that don't have a clear
"unavailable"-style label but do have a reliable "Add to Cart" button or
similar):

```json
{
  "urls": ["https://example.com/product"],
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
