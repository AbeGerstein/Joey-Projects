# Working with Claude across environments

The bot lives in two places once it's deployed:
1. **The Codespace** (this dev environment) — where major development and Claude collaboration happen
2. **The advisor's Windows laptop** — where the bot actually runs in production

Both are git clones of the same GitHub repo. This document explains the workflow for keeping them synchronized and getting Claude's help with issues that surface in production.

---

## The basic loop

```
                ┌──────────────────────┐
                │  Issue on laptop     │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │  Capture error +     │
                │  paste into Claude   │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │  Claude diagnoses    │
                │  in Codespace        │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │  Claude commits      │
                │  + pushes to GitHub  │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │  Laptop: git pull    │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │  Retry failing op    │
                └──────────────────────┘
```

The git remote (GitHub) is the single source of truth. Both environments stay in sync via push/pull.

---

## When to develop in Codespace vs on the laptop

| Activity | Where |
|---|---|
| Methodology changes, new patterns, scoring logic | Codespace |
| Adding tests, refactoring, code review | Codespace |
| Documentation updates | Codespace |
| Trying production with real Norgate data | Laptop only |
| Reviewing real daily reports | Laptop only |
| Fixing production-only bugs | Either — depends on the bug |

**Default to Codespace** for development. The laptop is a production environment — small risk of breaking the daily run if you mess something up. Only edit on the laptop directly when:
- You need real Norgate data to reproduce the issue
- You're physically with the advisor and need to demo a fix quickly
- The fix is a config change (which is in `config.toml`, gitignored, never in the repo)

---

## How to give Claude useful context about a laptop-side issue

When pasting an error into Claude, include:

1. **The exact command you ran** (e.g., `pnf-bot daily-run`)
2. **The full error message and traceback** (don't truncate)
3. **What you were doing right before** (just installed something? changed config? first run after a pull?)
4. **The git commit you're on** (`git log -1 --oneline`)
5. **Your OS** (Windows 10 / Windows 11 — they sometimes differ)
6. **Relevant log lines** from `logs/` directory if available

Bad: "the email isn't sending"
Good:
```
Running pnf-bot daily-run on Windows 11, commit 91a5362. Error after universe refresh succeeded:

Traceback (most recent call last):
  File ".venv\Lib\site-packages\smtplib.py", line 1023, in starttls
    raise SMTPNotSupportedError(...)
SMTPNotSupportedError: STARTTLS extension not supported by server.

Was working yesterday. Today's first run after I updated the venv with pip install --upgrade.
```

The second version gives Claude enough to diagnose in one shot.

---

## After Claude pushes a fix

On the laptop:

```
cd C:\Users\<username>\Documents\pnf-bot
git pull
```

If you've made local changes (typically only `config.toml`, but check), git pull will preserve gitignored files. If git complains about uncommitted changes in tracked files, that's unusual — see the section below on dealing with merge conflicts.

After pulling, **if dependencies changed**, reinstall:
```
.venv\Scripts\activate
pip install -e .[norgate]
```

Then retry whatever was failing.

---

## What if both environments have made changes?

This is the merge-conflict scenario. It happens if:
- You hot-fixed something on the laptop, committed, pushed
- Meanwhile Claude made a different change in Codespace, committed, pushed

Or vice versa.

**Recovery:**
1. On whichever environment is "behind" (didn't push first), `git pull --rebase`
2. Resolve any conflicts (git tells you which files)
3. Run the tests: `python -m pytest tests/`
4. Commit the resolution
5. Push

**Better: avoid it.** Before making changes on the laptop, always `git pull` first to see what Claude has done. Likewise, when starting a Codespace session, paste the laptop's current `git log -3 --oneline` so Claude knows the state.

---

## Common production-only issues (that you can't easily reproduce in Codespace)

These are the ones most likely to need real-laptop debugging:

1. **Norgate-specific data quirks** — symbols with edge cases, recent corporate actions, dividend adjustments. Codespace has no Norgate access.
2. **WeasyPrint / GTK runtime issues on Windows** — Codespace runs Linux; PDF generation has different requirements there.
3. **Windows Task Scheduler weirdness** — wake timers, sleep states, scheduled-task user permissions. Pure Windows-side.
4. **SMTP delivery to specific recipients** — Gmail behavior, spam filtering, attachment limits.
5. **Performance under real universe sizes** — Codespace runs synthetic data; real Norgate has 4,000+ tickers and longer histories.

For these, the loop has to involve the laptop. Either you debug there directly or you reproduce the issue, capture detailed logs, and pass them to Claude.

---

## Two Claude sessions, one project

You can run Claude Code on the laptop too (if you want AI assistance for laptop-side fixes). The model isn't shared between sessions, but they can both see the same repo via git.

**To onboard a new Claude session (on either end):**

The session should read these files first to understand the project:
1. `CLAUDE.md` (root of repo) — summary, conventions, common operations
2. `docs/00-project-outline.md` — phased plan with status
3. `docs/01-decisions-log.md` — full audit trail of decisions
4. `docs/research/norgate-data.md` — Norgate SDK reference

This is what's set up in [CLAUDE.md](../../CLAUDE.md). Any Claude session that opens the repo should automatically use it.

**To bring a fresh session up to speed on a specific in-progress task:**

Say something like:
> "I'm continuing work on the PnF Bot project. The most recent commit is [hash]. We're [doing X]. Read CLAUDE.md and the recent docs/01-decisions-log.md entries, then help me [Y]."

This lets the new Claude session quickly orient without you re-explaining the whole project.

---

## What NOT to do across environments

- **Don't commit `config.toml`** — it contains real credentials. It's gitignored; don't override.
- **Don't commit `data/pnf_bot.db`** or anything in `data/` — gitignored; database is per-environment.
- **Don't commit `out/`** — synthetic artifacts; gitignored.
- **Don't push without running tests first** — both environments rely on the test suite as a safety net. `python -m pytest tests/` before every push.
- **Don't change Norgate-related code on the laptop without testing in Codespace first** — the laptop is where Norgate IS configured; "testing" there means running against production data. Make changes in Codespace, push, pull to laptop, then test.
- **Don't share Gmail app passwords in chat** — even with Claude. Keep them in `config.toml` on the laptop only.

---

## Quick reference — the most common commands

On the laptop:
```
# Pull latest fixes
git pull

# Reinstall after deps change
.venv\Scripts\activate && pip install -e .[norgate]

# Run the tests
python -m pytest tests/

# Manual daily-run for debugging
pnf-bot daily-run

# Check git status
git log -3 --oneline
git status
```

In Codespace:
```
# Run the tests
python3 -m pytest tests/

# Run the smoke test (no Norgate needed)
python3 scripts/end_to_end_smoke.py

# Lint check
python3 -m ruff check src/pnf_bot tests

# Commit + push (after Claude makes changes)
git add -A
git commit -m "message"
git push origin main
```
