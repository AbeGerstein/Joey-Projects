# Troubleshooting guide

Common errors you might hit during deployment or operation, in order from setup-time issues to production-time issues. Each entry shows the error message you'll see, what's actually wrong, and how to fix it.

---

## Setup-time issues

### `python is not recognized as an internal or external command`

**Cause:** Python wasn't added to PATH during install.

**Fix:** Reinstall Python with the "Add python.exe to PATH" checkbox enabled on the first installer screen. Or, add it manually: Windows Settings → System → About → Advanced system settings → Environment Variables → edit PATH → add the Python install directory (typically `C:\Users\<user>\AppData\Local\Programs\Python\Python311\` plus its `Scripts\` subfolder).

### `pip install -e .[norgate]` fails with "Microsoft Visual C++ 14.0 or greater is required"

**Cause:** Some Python packages (numpy, pandas) include C extensions that need a C++ build toolchain on Windows.

**Fix:** Install "Microsoft C++ Build Tools" from <https://visualstudio.microsoft.com/visual-cpp-build-tools/>. During install, select "Desktop development with C++" workload. Reboot. Retry the pip install.

**Faster alternative:** install pre-built wheels by adding `--prefer-binary` to the pip command, or just upgrade pip first (`pip install --upgrade pip`) — newer pip versions are better at finding pre-built wheels.

### `pip install` fails because of a SSL certificate error

**Cause:** Some corporate networks intercept SSL traffic.

**Fix:** Try the install on a personal network (home WiFi or phone hotspot). If that's not an option, ask IT to allowlist `pypi.org` and `files.pythonhosted.org`.

---

## Norgate-related issues

### `NorgateNotConfiguredError: The norgatedata SDK is not installed`

**Cause:** The pip install didn't include the `[norgate]` extra.

**Fix:**
```
pip install -e .[norgate]
```

### `NorgateNotConfiguredError: Norgate SDK call failed: ...`

**Cause:** The SDK is installed but NDU isn't running (or isn't authenticated).

**Fix:**
1. Open NDU (system tray icon, or start menu)
2. Verify it shows "Up to date" or similar status
3. If NDU shows "Not signed in," sign in with subscriber credentials
4. If NDU is stuck mid-update, wait for it to finish
5. Retry the bot command

### `NorgateNotConfiguredError: ... database not yet built`

**Cause:** NDU finished installing but hasn't completed the initial database build.

**Fix:** Wait. The initial build for US Stocks Platinum can take 1–3 hours. Check NDU's progress indicator. The bot won't work until the build is complete.

### `list_universe()` returns 0 or very few symbols

**Cause:** NDU hasn't finished syncing.

**Fix:** Open NDU, click "Update Now," wait for completion. Then re-run `pnf-bot refresh-universe`.

### `fetch_ohlc('AAPL')` returns an empty DataFrame

**Cause:** Either the symbol doesn't exist in your NDU database (try a different symbol like SPY), or NDU's data is stale.

**Fix:** Run NDU's "Update Now" function. If still empty, contact Norgate support — there may be a subscription tier mismatch.

### Backfill is very slow

**Cause:** Norgate's SDK does single-ticker fetches; ~4000 tickers × 10 years can take 30–60 minutes.

**Fix:** This is normal on first backfill. Subsequent runs use incremental refresh (`refresh-prices`), which only fetches the latest bars and completes in 1–5 minutes.

---

## Database issues

### `sqlite3.OperationalError: database is locked`

**Cause:** Another process has the SQLite database file open (a previous bot run that didn't exit cleanly, or a DB browser tool).

**Fix:** Close any DB browser tools. Kill any stuck Python processes. Retry. If it persists, delete `data/pnf_bot.db-journal` (the WAL file) — but only if no bot process is currently running.

### `PermissionError: [Errno 13] Permission denied: 'data/pnf_bot.db'`

**Cause:** Windows file permissions or the file is open in another tool.

**Fix:** Close any application that might have the file open. Run the bot from a terminal opened as the same user who created the database. If running scheduled, make sure the Task Scheduler job runs as the same user.

---

## Email delivery issues

### `SMTPAuthenticationError: 535 5.7.8 Username and Password not accepted`

**Cause:** Wrong app password, OR you used the regular login password instead of an app password.

**Fix for Gmail SMTP:**
1. Verify 2-Factor Authentication is enabled on the Gmail account: <https://myaccount.google.com/security>
2. Generate a new app password at <https://myaccount.google.com/apppasswords>
3. Paste the 16-character password into `config.toml`'s `smtp_password` field (spaces in the password are OK, the bot strips them)
4. Make sure `smtp_user` matches the Gmail address you generated the app password for

**Fix for Yahoo SMTP:**
1. Verify Two-step verification is enabled at <https://login.yahoo.com/account/security>
2. Generate a new app password from "Other ways to sign in" → "Generate and manage app passwords"
3. Paste the 16-character password into `config.toml`'s `smtp_password` field
4. Make sure `smtp_user` matches the Yahoo address (e.g., `Jromero816@yahoo.com`)
5. Confirm `smtp_host = "smtp.mail.yahoo.com"` (not `smtp.gmail.com`)

### `SMTPSenderRefused: 553 ... not allowed`

**Cause:** Gmail SMTP doesn't allow sending from an address that doesn't match the authenticated account.

**Fix:** Set `smtp_from` to the same Gmail address as `smtp_user` (or to a domain you've verified with Gmail). Gmail won't let you spoof other addresses.

### `SMTPConnectError: ... Connection refused`

**Cause:** Network issue or firewall blocking outbound SMTP traffic on port 587.

**Fix:**
- Test from a different network (mobile hotspot, home WiFi) to rule out a corporate firewall
- Verify the Gmail SMTP host is `smtp.gmail.com` (not `smtp.googlemail.com` — both work but spelling matters)
- If port 587 is blocked, try port 465 with `smtp_use_tls = false` and let Gmail handle SSL/TLS

### Email arrives, but goes to spam

**Cause:** Gmail flags emails from unfamiliar senders or with attachments.

**Fix:**
- In the recipient's Gmail/Yahoo inbox, mark one of the emails as "Not Spam"
- Add the sender address to the recipient's contacts
- Consider setting up SPF/DKIM if sending from a custom domain (Gmail's free tier doesn't allow custom SPF easily)

### Email arrives but the PDF attachment is missing

**Cause:** The PDF generation step failed silently. The bot still sent the HTML body.

**Fix:** See "PDF generation fails" below.

---

## PDF generation issues

### `RuntimeError: WeasyPrint is not installed` or `OSError: cannot load library 'gobject-2.0-0'`

**Cause:** WeasyPrint's native GTK dependencies aren't installed on Windows.

**Fix:**
1. Install GTK runtime: <https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases>
2. During GTK install, check "Set up PATH environment variable"
3. **Reboot** — PATH changes need a restart to be picked up by all processes
4. Retry the bot

If still failing, see WeasyPrint's Windows docs: <https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows>

### PDF generates but charts are missing or look wrong

**Cause:** matplotlib's image generation failed silently.

**Fix:** Run the smoke test to verify chart rendering works in isolation:
```
python scripts/end_to_end_smoke.py
```
Open the resulting `out/smoke/smoke_report.pdf` — if the charts are visible there, the issue is with how the daily-run is passing data. If charts are missing in the smoke test too, see "matplotlib backend" notes below.

### `matplotlib: UserWarning: ... non-interactive backend`

**Not an error**, just a warning. The bot uses `matplotlib.use("Agg")` to render charts headlessly (no display required). The warning is normal.

---

## Scoring / pattern issues

### `pnf-bot daily-run` finishes but returns 0 candidates in both sections

**Cause:** Either the universe is empty (Norgate not synced), the price data is stale (universe loaded but backfill didn't run), or the chart patterns are genuinely not matching anything that day.

**Fix:**
1. Verify universe has tickers: `python -c "from pnf_bot.data import universe, config as c; cfg = c.load_config('config.toml'); print(len(universe.get_active_universe(cfg)))"`
2. Verify prices have been backfilled: open `data/pnf_bot.db` in a SQLite browser, check `daily_bars` row count
3. If both look OK, the bot may have legitimately found no matches that day. Try the smoke test to verify the scoring code itself works.

### Section A has many candidates but Section B is empty (or vice versa)

**Not an error.** This is market-dependent. In a strongly bullish market, many stocks are in momentum (Section B fills up); in a basing market, more are pre-momentum (Section A). Both 0 occasionally happens; only sustained 0s indicate a problem.

---

## Audit log issues

### Audit log shows `delivery_status = 'failed'`

**Look at `delivery_error`** in the same row to see the SMTP error message. Use the email troubleshooting section above to diagnose.

### Audit log files are accumulating to a large size

**Cause:** Each day produces an HTML (~150KB) and PDF (~120KB) archive file. Over a year, ~100MB of archives accumulate.

**Fix:** This is expected and required for compliance recordkeeping. The compliance doc specifies 5–7 year retention. If disk space becomes an issue, move older files to an external drive but keep them accessible.

---

## CLI issues

### `pnf-bot: command not found` after install

**Cause:** Either the venv isn't activated, or pip install didn't register the entry point.

**Fix:**
1. Verify venv is active: prompt should show `(.venv)`
2. If not, activate: `.venv\Scripts\activate`
3. If still not found, reinstall: `pip install -e .[norgate]`

### `ImportError: cannot import name 'X' from 'pnf_bot.Y'`

**Cause:** You have an outdated install. The bot was updated, but the entry-point binary points at an older version.

**Fix:**
```
pip install -e .[norgate] --force-reinstall
```

### CLI hangs and doesn't return

**Cause:** Likely waiting on a slow Norgate call or large fetch.

**Fix:** Wait. `backfill-prices` can take 30–60 minutes on first run. If you suspect it's truly stuck, Ctrl-C and check the logs. The Norgate SDK can occasionally block on slow disk I/O.

---

## When to ask Claude for help

For anything not covered here, see [working-with-claude.md](working-with-claude.md) for how to give Claude useful context so it can diagnose remotely.

---

## When to contact Norgate support

For anything specific to NDU itself (subscription issues, data quality concerns, missing symbols), contact Norgate directly: <https://norgatedata.com/contact-us.php>

For SMTP/email issues, contact Google Workspace / Gmail support if it's authentication-related. Most other issues are local config.
