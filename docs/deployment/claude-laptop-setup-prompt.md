# Claude Code laptop-setup prompt

**Audience: a Claude Code session running on the advisor's Windows laptop, tasked with deploying the PnF Bot to production.**

This document is your runbook. Read it top to bottom before doing anything. Then execute the phases in order. Each phase has a goal, the commands to run, what success looks like, and what to do if something fails.

The human operator is in the room with you and can answer questions, click through installers, and provide credentials. Anything labeled **🧑 HUMAN ACTION REQUIRED** means the human has to do that step; you should clearly tell them what to do and wait for them to confirm.

---

## Mission briefing

You are deploying **PnF Bot** — a Point and Figure stock screener that has already been built. The bot's code is complete and tested (213 tests pass in CI). Your job is to:

1. Get the code onto this Windows laptop from GitHub
2. Install Python dependencies
3. Configure Norgate Data and Gmail SMTP
4. Bootstrap the local database with historical OHLC
5. Verify one end-to-end manual run produces a real PDF email
6. Schedule it to run daily at 3 AM Mountain Time

Repository: <https://github.com/AbeGerstein/Joey-Projects>

The bot's authoritative documentation lives in the repo. Once you clone it, read in order:

1. `CLAUDE.md` (root) — orientation
2. `docs/deployment/runbook.md` — the human-readable runbook (this file is the Claude-readable version)
3. `docs/deployment/troubleshooting.md` — reference for any errors that surface

---

## Pre-flight checks

Before starting any phase, verify the basics:

```powershell
# What OS are we on?
[System.Environment]::OSVersion.VersionString

# Are we running with admin rights? (some installers need this)
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# Where are we?
Get-Location
```

Confirm with the human:
- This is the advisor's laptop (not yours)
- The advisor has internet connectivity
- The advisor has agreed to keep this laptop running 24/7 at their office
- The advisor knows you may need them to enter credentials at certain steps

If any of these are no, **stop** and clarify with the human before proceeding.

---

## Phase A — Repository and Python setup (automated)

**Goal:** clone the repo, install Python if needed, set up a virtual environment, install all dependencies.

### A.1 — Check if Python 3.11+ is installed

```powershell
python --version
```

**Expected:** `Python 3.11.x` or `Python 3.12.x`

**If "python is not recognized" or version < 3.11:**

🧑 **HUMAN ACTION REQUIRED**: Tell the human to:
1. Open <https://www.python.org/downloads/> in a browser
2. Download the latest Python 3.11 or 3.12 (64-bit installer for Windows)
3. Run the installer, **critically** checking "Add python.exe to PATH" on the first screen
4. Choose "Install Now"
5. Tell you when it's done

Then ask them to **open a new PowerShell terminal** (Python won't be on PATH in the current session). Re-run `python --version` to confirm.

### A.2 — Check if Git is installed

```powershell
git --version
```

**Expected:** `git version 2.x.x`

**If missing:**

🧑 **HUMAN ACTION REQUIRED**: download and install Git for Windows from <https://git-scm.com/download/win>. Accept all defaults. Have the human reopen the terminal.

### A.3 — Clone the repository

Pick a stable install location. The Documents folder is a good default:

```powershell
cd $HOME\Documents
git clone https://github.com/AbeGerstein/Joey-Projects.git pnf-bot
cd pnf-bot
```

**Verify:**

```powershell
Get-ChildItem
```

You should see `CLAUDE.md`, `README.md`, `src`, `tests`, `docs`, `pyproject.toml`, `config.toml.example`, etc.

**Now read the orientation file:**

```powershell
Get-Content CLAUDE.md
```

Read it. It tells you everything about the project's structure, conventions, hard constraints. You're now oriented.

### A.4 — Create the Python virtual environment

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\activate
```

After activation, your prompt should show `(.venv)` as a prefix. **Every subsequent command in this guide assumes the venv is active.** If the human opens a new terminal at any point, they need to re-activate it from the project root:

```powershell
cd $HOME\Documents\pnf-bot
.venv\Scripts\activate
```

### A.5 — Install the bot and dependencies

```powershell
pip install --upgrade pip
pip install -e .[norgate,dev]
```

This downloads and installs pandas, numpy, matplotlib, sqlalchemy, pydantic, click, weasyprint, jinja2, the norgatedata SDK, and dev tools (pytest, ruff). Expect 2–5 minutes.

**If the install fails** with "Microsoft Visual C++ 14.0 or greater is required":

🧑 **HUMAN ACTION REQUIRED**: install Microsoft C++ Build Tools from <https://visualstudio.microsoft.com/visual-cpp-build-tools/>. During install, select "Desktop development with C++" workload. Reboot. Retry the pip install. (See `docs/deployment/troubleshooting.md` for full detail.)

### A.6 — Verify the install

```powershell
pnf-bot version
```

Should print `pnf-bot 0.0.1`.

Run the test suite to verify everything works:

```powershell
python -m pytest tests/
```

**Expected:** `213 passed`. If any test fails, stop and investigate before continuing.

Run the smoke test to verify the full pipeline works without Norgate:

```powershell
python scripts/end_to_end_smoke.py
```

**Expected:** the script generates `out/smoke/smoke_report.html` and `out/smoke/smoke_report.pdf` and exits cleanly.

If the PDF generation fails with a WeasyPrint error about GTK, proceed to Phase B. Otherwise skip Phase B.

### Phase A complete — checkpoint

Report to the human:
- Python version installed
- Repo cloned to `<path>\pnf-bot`
- Venv active, all 213 tests passing
- Smoke test produced HTML + PDF artifacts

---

## Phase B — WeasyPrint GTK runtime (Windows-specific, may be skippable)

**Goal:** ensure WeasyPrint can render PDFs on Windows by installing the GTK runtime.

**Skip this phase if** the smoke test in A.6 produced a PDF successfully. WeasyPrint sometimes finds the necessary libraries automatically.

**Otherwise:**

🧑 **HUMAN ACTION REQUIRED**:
1. Open <https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases> in a browser
2. Download the latest `gtk3-runtime-*-ts-win64.exe`
3. Run the installer. On the relevant screen, **check "Set up PATH environment variable to include GTK+"**
4. **Reboot the laptop** — PATH changes need a full restart to be picked up by all processes

After reboot, the human reopens a terminal, reactivates the venv, and tells you it's done. Then re-run:

```powershell
python scripts/end_to_end_smoke.py
```

The PDF should generate successfully now.

---

## Phase C — Norgate subscription (HUMAN ONLY)

**Goal:** the advisor's Norgate subscription is active and credentials are in hand.

🧑 **HUMAN ACTION REQUIRED**:
1. Check with the advisor: is the Norgate subscription already active? If yes, ask for the subscriber credentials and skip to Phase D.
2. If no, walk through subscribing:
   - Visit <https://norgatedata.com>
   - Subscribe to **US Stocks Platinum** ($630/year as of May 2026). Do NOT subscribe to lower tiers — Platinum is required for the bot's locked decisions.
   - Use the advisor's preferred payment method
   - Wait for the welcome email with credentials

You (Claude) cannot do this step. Wait for the human to confirm credentials are in hand.

---

## Phase D — Norgate Data Updater install + initial sync (mixed)

**Goal:** NDU is installed on this laptop, authenticated, and has completed its initial database build.

### D.1 — Install NDU

🧑 **HUMAN ACTION REQUIRED**: download Norgate Data Updater from the link in the Norgate welcome email (or from the Norgate website's downloads page). Run the installer. Accept defaults.

### D.2 — Authenticate NDU

🧑 **HUMAN ACTION REQUIRED**: launch NDU. On first run it asks for subscriber credentials. Have the human sign in.

### D.3 — Let NDU complete the initial database build

NDU starts building its local data store automatically after authentication. **This is the slow step — 1 to 3 hours depending on bandwidth.**

While waiting, you can proceed with Phase E (Gmail SMTP setup) and Phase F.1 (creating config.toml). Don't proceed to Phases F.2 through H until NDU shows "Up to date" or equivalent.

### D.4 — Configure NDU for unattended operation

When NDU's initial build completes:

🧑 **HUMAN ACTION REQUIRED**: in NDU's settings (gear icon or File → Preferences):
- Enable **"Start NDU with Windows"** (so it auto-starts on boot)
- Enable **"Minimize to system tray on startup"** (so it stays out of the way)
- Save and restart NDU once to confirm it minimizes correctly

### D.5 — Configure Windows power settings

The laptop must not sleep overnight:

🧑 **HUMAN ACTION REQUIRED**:
1. Open Windows Settings → System → Power & sleep
2. Set "When plugged in, PC goes to sleep after" to **Never**
3. Optionally set the screen-off setting to **Never** too
4. Click "Additional power settings" → "Change plan settings" → "Change advanced power settings"
5. Under Sleep → Allow wake timers → **Enable**
6. Under Hard disk → Turn off hard disk after → **Never**

### D.6 — Verify NDU is reachable from the bot

```powershell
python -c "from pnf_bot.data import norgate; print(len(norgate.list_universe('US Equities')))"
```

**Expected:** a number, typically 6,000+ (this is the raw count including ETFs/preferreds, before our common-stock filter).

**If you get `NorgateNotConfiguredError`:**

The most common causes:
- NDU isn't running (check the system tray for the NDU icon)
- NDU hasn't finished the initial build (check the NDU GUI for progress)
- Subscription isn't active (check the NDU status panel)

Walk through with the human, retry the test after each fix attempt.

### Phase D complete — checkpoint

Report to the human:
- NDU installed and authenticated under the advisor's account
- Initial database build complete
- NDU set to auto-start with Windows
- Power settings configured (no sleep)
- `norgate.list_universe()` returns 6,000+ symbols

---

## Phase E — SMTP setup (HUMAN ONLY, can run in parallel with D.3)

**Goal:** an email account is ready to send the daily report from, with an app password the bot can use. Either Yahoo or Gmail works; ask the human which the advisor uses.

🧑 **HUMAN ACTION REQUIRED**:

### If the advisor uses Yahoo (most likely path — Jromero816@yahoo.com is on Yahoo)

1. Visit <https://login.yahoo.com/account/security>
2. Sign in to the Yahoo account that will SEND emails (the advisor's own Yahoo account is fine — sending to himself is normal)
3. Enable **Two-step verification** if not already on (Yahoo requires it for app passwords)
4. Find **"Generate and manage app passwords"** (sometimes under "Other ways to sign in")
5. Generate a new app password. Name it "PnF Bot"
6. Yahoo shows a 16-character password — copy it (Yahoo only shows it once)

SMTP settings for Yahoo:
- `smtp_host = "smtp.mail.yahoo.com"`
- `smtp_port = 587`
- `smtp_use_tls = true`

### If using Gmail instead

1. Pick a Gmail account to send from (the advisor's, a dedicated bot account, or the developer's)
2. Ensure 2-Factor Authentication is enabled on that account
3. Visit <https://myaccount.google.com/apppasswords>
4. Generate a new app password named "PnF Bot"
5. Copy the 16-character password (Google only shows it once)

SMTP settings for Gmail:
- `smtp_host = "smtp.gmail.com"`
- `smtp_port = 587`
- `smtp_use_tls = true`

You (Claude) cannot do this step. Wait for the human to confirm they have the app password and tell you which provider (Yahoo or Gmail).

---

## Phase F — config.toml fill-in

**Goal:** `config.toml` exists in the project root with all the real values filled in.

### F.1 — Create config.toml from the example

```powershell
Copy-Item config.toml.example config.toml
```

### F.2 — Fill in the values

The defaults in `config.toml.example` already match the locked project decisions (recipient email, top-10 sections, $1 floor, RSP benchmark, 3 AM MT scheduler, etc.). The only fields you need to change are in the `[email]` section.

Open `config.toml` (Claude can use the Edit tool):

```toml
[email]
smtp_host = "smtp.gmail.com"
smtp_port = 587
smtp_user = "<the Gmail address from Phase E>"
smtp_password = "<the 16-char app password from Phase E>"
smtp_from = "PnF Bot <<the Gmail address from Phase E>>"
smtp_use_tls = true
```

Replace the three `<...>` placeholders with the real values the human provided.

**Critical:** the `smtp_password` is the 16-character app password, NOT the human's regular Gmail password. Gmail rejects regular passwords for SMTP.

### F.3 — Validate the config parses

```powershell
python -c "from pnf_bot.config import load_config; cfg = load_config('config.toml'); print('Config OK; recipient:', cfg.report.recipient_email)"
```

**Expected:** `Config OK; recipient: Jromero816@yahoo.com`

**If validation fails** (most likely an EmailStr issue or malformed TOML): the error message will say exactly what's wrong. Fix and retry.

### Phase F complete — checkpoint

Report to the human:
- config.toml created
- SMTP credentials filled in
- Config parses successfully

**Critical:** do NOT commit `config.toml` to git. It's gitignored, but double-check with:

```powershell
git status
```

You should NOT see `config.toml` in the modified files. If you do, the gitignore isn't working — investigate.

---

## Phase G — Database bootstrap

**Goal:** the local SQLite database has the universe of tickers loaded and 10 years of historical OHLC backfilled.

**Prerequisites:** Phase D complete (NDU running with data).

### G.1 — Initialize the database schema

```powershell
pnf-bot init-db
```

**Expected:** `Database schema initialized at data\pnf_bot.db`

### G.2 — Refresh the universe

```powershell
pnf-bot refresh-universe
```

This pulls every active US common stock from Norgate (filtering out ETFs, preferreds, BDCs, etc. via the subtype check) and persists their metadata to the local database.

**Expected duration:** 2–10 minutes.

**Expected output:** `Active tickers in universe: 4000+` (exact number varies; typically 3,500–4,500).

### G.3 — Backfill 10 years of OHLC

```powershell
pnf-bot backfill-prices
```

**This is the slow step. Expect 15–60 minutes.** The bot fetches per-ticker history one symbol at a time from Norgate's local data store.

**Expected output:** `Inserted <large number> historical bars.` Number is typically in the millions for 4000 tickers × 10 years.

If this seems hung (no progress for 10+ minutes), check NDU — its database might have an issue. The Norgate SDK can occasionally block on slow disk I/O during long iterative pulls.

### Phase G complete — checkpoint

Report to the human:
- Database initialized
- Universe loaded with 4,000+ active tickers
- 10 years of OHLC backfilled

Verify with a quick sanity check:

```powershell
python -c "
from pnf_bot.data import storage
from sqlalchemy import select, func
with storage.get_session('data/pnf_bot.db') as s:
    n_tickers = s.execute(select(func.count(storage.Ticker.symbol))).scalar()
    n_bars = s.execute(select(func.count()).select_from(storage.DailyBar)).scalar()
    print(f'Tickers: {n_tickers:,}; daily bars: {n_bars:,}')
"
```

---

## Phase H — First manual daily-run test

**Goal:** the full pipeline produces a daily report PDF and emails it to the advisor.

### H.1 — Run the full pipeline manually

```powershell
pnf-bot daily-run
```

**This is the moment of truth.** The bot:
1. Refreshes the latest day's prices (1–5 minutes)
2. Scores every active ticker (5–15 minutes)
3. Renders charts and the HTML/PDF report
4. Sends the email
5. Persists everything to the audit log

**Expected final output:**

```
Daily run complete. Section A: <n>, Section B: <m>, delivery: sent
```

**If `delivery: failed`:** the email failed. Check the audit log:

```powershell
python -c "
from pnf_bot.data import storage
from sqlalchemy import select
with storage.get_session('data/pnf_bot.db') as s:
    rows = s.execute(select(storage.ReportArchive).order_by(storage.ReportArchive.id.desc()).limit(1)).scalars().all()
    for r in rows:
        print('Status:', r.delivery_status)
        print('Error:', r.delivery_error)
        print('PDF path:', r.pdf_path)
"
```

The `delivery_error` field tells you what went wrong. Cross-reference with `docs/deployment/troubleshooting.md` → "Email delivery issues."

### H.2 — Verify the email arrived

🧑 **HUMAN ACTION REQUIRED**: have the human check `Jromero816@yahoo.com` (or whatever recipient is in `config.toml`) for:
- Subject: `Daily PnF stock report — YYYY-MM-DD`
- Attachment: `daily_pnf_report.pdf` or similar (~100–500KB)
- Inline HTML body that displays charts and candidate cards

If it landed in spam, ask the human to mark it "Not Spam" and add the sender to contacts.

If it didn't arrive at all after 5 minutes:
- Re-check `delivery_status` in the audit log
- If it says `sent`, check the recipient's spam folder
- If it says `failed`, look at `delivery_error`

### H.3 — Inspect the report

Have the human open the PDF and look at:
- Top of report: "Daily PnF stock report" header
- DISCLAIMER block in yellow
- (Maybe) "New Patterns from Last Night" callout if any fresh patterns
- "Section A — Pre-Momentum Candidates" with N stocks
- "Section B — In-Momentum Candidates" with M stocks
- Each candidate card has a P&F chart, RS chart, signal history, suggested entry/stop

If the layout looks broken, the charts are missing, or anything else looks wrong: report what you see, save a copy of the PDF, then we'll diagnose.

### Phase H complete — checkpoint

Report to the human:
- Daily run completed with N + M candidates
- Email delivered (verified by human checking inbox)
- PDF inspection passed

---

## Phase I — Windows Task Scheduler (HUMAN-DRIVEN, Claude guides)

**Goal:** the bot runs automatically every weekday at 3:00 AM Mountain Time.

You (Claude) can't directly automate Windows Task Scheduler through GUI, but you can generate an XML import that the human can load.

### I.1 — Walk the human through the GUI

Tell the human:
1. Open **Task Scheduler** (search in Start menu)
2. Right pane → **Create Basic Task**
3. Name: `PnF Bot Daily Run`
4. Description: `Runs the PnF Bot screener every weekday morning at 3 AM Mountain Time`
5. Trigger: **Daily**, start time **3:00:00 AM**, recur every 1 day
6. Action: **Start a program**
7. Program/script: `<full path to pnf-bot.exe>` — to find this, run `(Get-Command pnf-bot).Source` and copy the output
8. Arguments: `daily-run`
9. Start in: `<full path to pnf-bot project root>` — output of `Get-Location` from inside the project
10. Click Finish

### I.2 — Configure the task's advanced properties

1. Right-click the new task → **Properties**
2. **Conditions** tab:
   - **Uncheck** "Start the task only if the computer is on AC power"
3. **Settings** tab:
   - **Check** "Wake the computer to run this task"
   - **Check** "Run task as soon as possible after a scheduled start is missed" (in case of brief downtime)
4. **General** tab:
   - **Check** "Run whether user is logged on or not" (allows the task to run when the screen is locked)
   - Click OK; Windows will ask for the user's password — that's expected

### I.3 — Test the scheduled task

Right-click the task → **Run**. This triggers an immediate test execution. Watch the task's "Last Run Result" — it should show `0x0` (success) within a few minutes.

You can also check that the bot ran by looking at the audit log — there should be a new row added in the last few minutes.

### Phase I complete — final checkpoint

Report to the human:
- Task scheduled for 3:00 AM Mountain Time daily
- Wake-on-timer enabled
- Test run succeeded
- Audit log shows the test execution

---

## Done — final handoff

The bot is now in production. Summarize for the human:

```
Deployment complete. Summary:
- Code installed at: <path>
- Database at: <path>\data\pnf_bot.db
- Reports archived at: <path>\reports\archive\
- Logs at: <path>\logs\
- Email sender: <smtp_user>
- Email recipient: Jromero816@yahoo.com
- Scheduled: 3:00 AM Mountain Time daily

Next steps for the advisor:
1. Watch for the first scheduled email tomorrow morning at ~8 AM MT
2. Email goes to spam? Mark as "Not Spam" and add sender to contacts
3. Weekly: developer should run `update_forward_returns` (see docs/deployment/maintenance.md)
4. Monthly: developer reviews the scoreboard
5. Any issues: contact the developer with the exact error message; the developer will use Claude in Codespace to diagnose and push a fix
```

Then make sure to:
- Show the human where the audit log lives so they can see the trail
- Show them how to manually trigger a run (`pnf-bot daily-run`) if they want to test
- Tell them the laptop must stay powered on with NDU running 24/7

---

## Reference — when things go wrong

If anything in this guide breaks:
1. Read `docs/deployment/troubleshooting.md` — most common issues are covered there
2. If the issue isn't covered, capture the exact error message + traceback
3. Tell the human to either:
   - Push the issue back to the developer in the Codespace conversation (the cross-environment workflow in `docs/deployment/working-with-claude.md`)
   - OR, if you're authorized to commit fixes from this laptop session, diagnose, fix, run tests, commit, push, and continue

When you commit from the laptop:
- Always run `python -m pytest tests/` before pushing
- Use the project's commit message style (see `git log --oneline -10` for examples)
- Don't commit `config.toml`, `data/`, `out/`, or `logs/` — these are gitignored

---

## What you (Claude) should NOT do

- **Don't enter the advisor's Norgate credentials, Gmail password, or any other secret.** Always ask the human to do that themselves.
- **Don't commit `config.toml`** — it has real credentials. Verify `git status` shows it as untracked.
- **Don't skip the test suite.** Always run `python -m pytest tests/` after any code change before committing.
- **Don't change the locked decisions** (recipient email, $1 floor, 10+10 sections, 3 AM MT scheduler) without asking the human first. They're in `docs/01-decisions-log.md`.
- **Don't push directly to `main`** without verifying tests pass — see the working-with-claude.md doc.
- **Don't proceed past a failed phase** — stop, ask the human, diagnose. Better to halt and clarify than to leave the deployment in a broken half-state.

Good luck. The repo is well-documented; lean on the docs/ tree whenever something feels uncertain.
