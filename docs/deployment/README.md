# Deployment documentation

Everything you need to take the bot from "code in a repo" to "running daily on the advisor's Windows laptop."

Read in this order:

1. **[runbook.md](runbook.md)** — step-by-step setup procedure for a human operator. The complete deployment from a blank Windows laptop to a scheduled daily run. Allow a few hours; most of that is Norgate's initial database build.

2. **[claude-laptop-setup-prompt.md](claude-laptop-setup-prompt.md)** — the same setup procedure, written for a Claude Code session running on the laptop to follow autonomously. **Use this if you're opening Claude Code on the laptop to automate deployment.** Tell that session to read `CLAUDE.md` first, then this file, then execute the phases in order.

3. **[troubleshooting.md](troubleshooting.md)** — every error you might hit during deployment or operation, with what's wrong and how to fix it.

4. **[maintenance.md](maintenance.md)** — weekly, monthly, quarterly, and annual operational tasks. Most importantly: the weekly `update_forward_returns` call that populates live performance data.

5. **[working-with-claude.md](working-with-claude.md)** — how to use Claude productively across the Codespace dev environment and the laptop production environment. The error-to-fix loop, when to develop where, common merge-conflict scenarios.

---

## Status snapshot

As of 2026-05-18:
- **Code:** functionally complete, 213 tests passing, ready for deployment
- **Norgate:** subscription not yet active; advisor will activate at deployment time
- **Email:** SMTP infrastructure built and tested locally; needs Gmail app password configuration at deployment time
- **Compliance:** scope cleared by advisor; ongoing posture documented in [../compliance.md](../compliance.md)

---

## Pre-deployment checklist

Before opening the runbook, make sure you have:

- [ ] Access to the advisor's Windows laptop (admin user)
- [ ] The advisor's Norgate subscription credentials
- [ ] A Gmail account for SMTP (yours or the advisor's)
- [ ] About 3–4 hours for the initial setup (most of it waiting on the Norgate database build)
- [ ] The advisor's commitment to keep the laptop powered on and connected to the internet 24/7

If any of these are missing, gather them before starting.
