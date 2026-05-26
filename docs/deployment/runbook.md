# Deployment runbook — advisor's Windows laptop

The complete, step-by-step procedure for deploying PnF Bot to the advisor's laptop. Read every step before starting. The whole process takes a few hours on first run (mostly because Norgate's initial database build is long).

**Target host:** Advisor's Windows laptop, kept running at his office, network always available.

---

## Phase 1 — Prerequisites (one-time setup, before Norgate)

### 1.1 Verify Windows version and admin access

- Windows 10 or Windows 11 (64-bit). Confirm with: `winver` from the Run dialog.
- The user account installing software needs **admin privileges** for some installers (Python, Norgate Data Updater, GTK runtime for WeasyPrint).

### 1.2 Install Python 3.11 or newer

1. Visit <https://www.python.org/downloads/>
2. Download Python 3.11 or 3.12 (64-bit installer)
3. Run the installer. **Critical:** check "Add python.exe to PATH" on the first installer screen.
4. Choose "Install Now" for the default install (Program Files location).
5. Verify install: open a new PowerShell or Command Prompt and run:
   ```
   python --version
   ```
   Should print `Python 3.11.x` or `3.12.x`. If "python is not recognized," reopen the terminal or reboot — PATH didn't refresh.

### 1.3 Install Git

1. Visit <https://git-scm.com/download/win>
2. Download and run the 64-bit Git installer
3. Accept the default options. Click through to install.
4. Verify: open a new terminal and run:
   ```
   git --version
   ```
   Should print `git version 2.x.x`.

### 1.4 Install WeasyPrint native dependencies (Windows-specific)

WeasyPrint generates PDFs and depends on GTK runtime libraries that don't come with Windows. Install them:

1. Visit <https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases>
2. Download the latest `gtk3-runtime-x.x.x-x-x-x-ts-win64.exe`
3. Run the installer. Choose "Set up PATH environment variable to include GTK+" on the relevant screen.
4. Reboot the laptop. WeasyPrint needs the libraries on PATH and a reboot ensures everything is picked up.

If WeasyPrint still fails to import after this, see [troubleshooting.md](troubleshooting.md) → "PDF generation fails."

### 1.5 Clone the bot repository

1. Open PowerShell or Command Prompt
2. Navigate to where you want the bot installed. Recommended:
   ```
   cd C:\Users\<username>\Documents
   ```
3. Clone the repo:
   ```
   git clone https://github.com/AbeGerstein/Joey-Projects.git pnf-bot
   cd pnf-bot
   ```

### 1.6 Create a Python virtual environment

Isolate the bot's Python dependencies from the system Python:
```
python -m venv .venv
```

Activate it (Windows):
```
.venv\Scripts\activate
```

You should see `(.venv)` prefix on the prompt. **Run this activation every time you open a new terminal for the bot.**

### 1.7 Install the bot and dependencies

With the venv active:
```
pip install -e .[norgate,dev]
```

This installs the bot in editable mode plus the Norgate SDK and dev tools. Takes 1–3 minutes (downloads pandas, numpy, matplotlib, etc.).

Verify:
```
pnf-bot version
```
Should print `pnf-bot 0.0.1`.

---

## Phase 2 — Norgate setup

### 2.1 Subscribe to Norgate Data

1. Visit <https://norgatedata.com>
2. Subscribe to **US Stocks Platinum** ($630/year as of 2026-05). Don't subscribe to the lower tiers — Platinum is required for historical index constituents and is the project's locked choice.
3. You'll receive credentials by email.

### 2.2 Install Norgate Data Updater (NDU)

1. From the email Norgate sent you, follow the link to download NDU.
2. Run the installer. Accept defaults.
3. On first launch, NDU asks for your subscriber credentials. Sign in.

### 2.3 Let NDU build the initial database

This is the slow step. NDU downloads roughly 30 years of US equity data to your local disk:

1. After signing in, NDU starts building automatically.
2. Watch the progress in the NDU GUI. It can take **1–3 hours** depending on bandwidth.
3. **Do not close NDU during this build.** Minimize it if you need to use the laptop for other things.
4. When build completes, NDU's status changes to "Up to date" or similar.

### 2.4 Configure NDU for unattended operation

The bot needs NDU running at all times to access data. Configure it:

1. Open NDU settings (gear icon or File → Preferences)
2. **Enable "Start NDU with Windows"** — so it auto-starts on boot
3. **Enable "Minimize to system tray on startup"** — so it stays out of the way
4. **Disable "Show splash screen"** — optional
5. Save and restart NDU to confirm it minimizes correctly

### 2.5 Configure Windows power settings

The laptop must not sleep overnight or the bot will fail:

1. Open Windows Settings → System → Power & sleep
2. Set "When plugged in, PC goes to sleep after" to **Never**
3. Optionally set "When plugged in, turn off after" to **Never** for the screen too
4. Click "Additional power settings" → "Change plan settings" → "Change advanced power settings"
5. Under "Sleep" → "Allow wake timers" → set to **Enable**
6. Under "Hard disk" → "Turn off hard disk after" → set to **Never**

---

## Phase 3 — Bot configuration

### 3.1 Set up SMTP credentials (Gmail or Yahoo)

The bot sends email via SMTP — either Gmail or Yahoo works. The advisor uses Yahoo (Jromero816@yahoo.com), so it's simplest to send FROM the same Yahoo account, since he already has it and there's no second account to manage. Pick whichever you prefer:

#### Option A — Yahoo SMTP (recommended if the advisor uses Yahoo)

1. Visit <https://login.yahoo.com/account/security>
2. Sign in as the Yahoo account you want emails to send FROM (the advisor's Jromero816@yahoo.com is the natural choice)
3. **Enable Two-step verification** if not already on (required for app passwords)
4. Find **"Generate and manage app passwords"** or **"Other ways to sign in"** → app passwords
5. Generate a new app password. Name it "PnF Bot." Yahoo gives you a 16-character password (similar format to Gmail's app passwords).
6. Copy this password — Yahoo only shows it once.

#### Option B — Gmail SMTP

1. Visit <https://myaccount.google.com/apppasswords>
2. Sign in with the Gmail account you want emails to come FROM
3. If 2-Factor Authentication isn't enabled on that account, enable it first (Google requires 2FA for app passwords)
4. Create a new app password. Name it "PnF Bot." Google gives you a 16-character password like `abcd efgh ijkl mnop`.
5. Copy this password. You'll paste it into `config.toml` next.

### 3.2 Create config.toml from the example

```
copy config.toml.example config.toml
```

### 3.3 Fill in config.toml

Open `config.toml` in any text editor (Notepad, VS Code, etc.) and fill in:

```toml
[data]
db_path = "data/pnf_bot.db"
min_price = 1.00
backfill_years = 10

[norgate]
universe_watchlist = "US Equities"
price_adjustment = "TotalReturn"
benchmark_symbol = "RSP"

[scoring]
section_a_top_n = 10
section_b_top_n = 10

[report]
recipient_email = "Jromero816@yahoo.com"
subject_line = "Daily PnF stock report"
delivery_time = "08:00"
delivery_timezone = "America/Denver"
archive_dir = "reports/archive"

# [email] — choose ONE of the two options below based on which SMTP provider you set up in 3.1

# Option A — Yahoo SMTP (if sending from the advisor's Yahoo account)
[email]
smtp_host = "smtp.mail.yahoo.com"
smtp_port = 587
smtp_user = "Jromero816@yahoo.com"                # ← the Yahoo address sending FROM
smtp_password = "<YAHOO_16_CHAR_APP_PASSWORD>"    # ← replace
smtp_from = "PnF Bot <Jromero816@yahoo.com>"      # ← match smtp_user's address
smtp_use_tls = true

# Option B — Gmail SMTP (if sending from a Gmail account)
# [email]
# smtp_host = "smtp.gmail.com"
# smtp_port = 587
# smtp_user = "<YOUR_GMAIL_ADDRESS>@gmail.com"    # ← replace
# smtp_password = "<GMAIL_16_CHAR_APP_PASSWORD>"  # ← replace
# smtp_from = "PnF Bot <<YOUR_GMAIL_ADDRESS>@gmail.com>"  # ← replace
# smtp_use_tls = true

[scheduler]
run_time = "03:00"
run_timezone = "America/Denver"

[logging]
log_dir = "logs"
log_level = "INFO"
```

**Critical:** the values that need replacement are the three `<YOUR_...>` placeholders in the `[email]` section. Everything else can stay at the defaults.

Save and close.

### 3.4 Initialize the database

```
pnf-bot init-db
```

Should print:
```
Database schema initialized at data\pnf_bot.db
```

### 3.5 Verify Norgate connectivity

Before the slow backfill, verify the SDK can reach Norgate:
```
python -c "from pnf_bot.data import norgate; print(len(norgate.list_universe('US Equities')))"
```

Expected: a number (likely 6,000+ — the total US equities count including ETFs/preferreds). If you see an error, see [troubleshooting.md](troubleshooting.md) → "Norgate not configured."

### 3.6 Refresh the universe

```
pnf-bot refresh-universe
```

This pulls every common-stock symbol (filtered by subtype1=Equity / subtype2=Operating/Holding) and persists metadata to the local database. Takes 1–5 minutes depending on universe size.

Expected output: `Active tickers in universe: 4000+` (number varies day to day).

### 3.7 Backfill historical prices

```
pnf-bot backfill-prices
```

This is the long step. The bot fetches 10 years of daily OHLC for every active ticker. Expect **15–60 minutes** depending on bandwidth and CPU.

Expected output: `Inserted <large number> historical bars.`

You can let this run in the background.

---

## Phase 4 — First production run

### 4.1 Manual test run

Run the full pipeline once manually to verify everything works end-to-end:
```
pnf-bot daily-run
```

This should:
1. Refresh latest prices (fast — just yesterday's bars)
2. Run scoring across the universe (5–15 minutes for ~4000 tickers)
3. Render the HTML and PDF
4. Email the report to `Jromero816@yahoo.com`
5. Persist to the audit log

Expected final output:
```
Daily run complete. Section A: <n>, Section B: <m>, delivery: sent
```

### 4.2 Verify the email arrived

- Check `Jromero816@yahoo.com` inbox for "Daily PnF stock report — YYYY-MM-DD"
- The PDF attachment should be ~100–500KB
- Open it and inspect — there should be charts, candidate cards, the DISCLAIMER block at the top

### 4.3 Verify the audit log

Check that the audit row was created:
```
python -c "
from pnf_bot.data import storage
from sqlalchemy import select
with storage.get_session('data/pnf_bot.db') as s:
    rows = s.execute(select(storage.ReportArchive)).scalars().all()
    for r in rows:
        print(r.generated_at, r.report_date, r.delivery_status, r.pdf_path)
"
```

You should see one row with delivery_status='sent'.

---

## Phase 5 — Scheduled daily operation

### 5.1 Create a Windows Task Scheduler job

1. Open Task Scheduler (search in Start menu)
2. Click "Create Basic Task" in the right pane
3. Name: `PnF Bot Daily Run`
4. Description: `Runs the PnF Bot screener every weekday morning`
5. Trigger: Daily, 3:00 AM, recur every 1 day
6. Action: Start a program
   - Program/script: `C:\Users\<username>\Documents\pnf-bot\.venv\Scripts\pnf-bot.exe`
   - Arguments: `daily-run`
   - Start in: `C:\Users\<username>\Documents\pnf-bot`
7. Click Finish
8. Open the task's properties, go to Conditions tab, **uncheck "Start the task only if the computer is on AC power"**
9. Under Settings tab, **check "Wake the computer to run this task"**
10. Save

### 5.2 Verify the scheduled task

The next morning, check:
- The advisor's inbox for the report email (should arrive shortly after 3 AM MT once the run completes)
- The bot's audit log for the day's row
- The bot's log files in `logs/` if anything went wrong

---

## Phase 6 — Hand-off to the advisor

Once the first scheduled run succeeds:

1. Show the advisor the email format
2. Walk through the per-candidate sections in the PDF
3. Show him how to find the audit log (in case compliance ever asks)
4. Tell him what to do if the email doesn't arrive (see [troubleshooting.md](troubleshooting.md))
5. Provide his contact for ongoing feedback / change requests

---

## Phase 7 — Ongoing maintenance

See [maintenance.md](maintenance.md) for the weekly / monthly / quarterly tasks that keep the bot calibrated. The most important: run `update_forward_returns` weekly to populate live performance data.
