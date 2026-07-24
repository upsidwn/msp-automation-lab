# Notes

Working notes and standards for this repo — security, tooling, AI usage,
project conventions. Not gospel, just what I want to keep consistent as
this grows.

---

## Project structure

Each automation project gets its own folder:

```
project-name/
  README.md
  documentation/
  source/
  examples/
  tests/
```

---

## Security

- Never hardcode creds. Env vars or Ansible Vault.
- Read-only accounts for anything that just collects info.
- Don't log passwords/tokens/API keys.
- Don't store customer PII unless there's a real reason to, and encrypt it
  if you do.
- Real collector output never gets committed — serials, hostnames, IPs,
  etc. from actual gear stay local (`examples/*.json`/`*.csv` are
  gitignored). Test fixtures are sanitized/fake data, not real captures,
  so the test suite still runs for anyone without the actual hardware.
- Before every commit: `git diff` / `git status` — check nothing sensitive
  snuck in.
- If a secret leaks into a commit anyway: rotate it immediately, assume
  it's burned.

---

## Automation principles

- Idempotent where possible — running it twice shouldn't double the
  damage.
- Automate the boring/repetitive stuff, not the judgment calls.
- Fail loudly, not silently — log what happened, what failed, why.
- Test the unhappy path too (bad creds, unreachable device, timeouts),
  not just the demo path.

---

## Tech stack (and why)

- **Python** — most automation logic, API integrations, AI glue
- **Ansible** — network device automation, config management (agentless)
- **Bash** — quick scripts, environment setup
- **Docker** — local dev, running supporting services
- **Terraform** — IaC, mostly for later cloud stuff
- **Git/GitHub** — version control, issues, PRs

---

## AI usage

Using AI (Claude/LLMs) here for: drafting docs, summarizing notes,
boilerplate code, brainstorming approach. Not for: making unsupervised
changes to real infrastructure, or as a source of truth I don't
double-check.

Rule of thumb: AI drafts, I review before anything ships or touches a
real device.

Don't feed it real credentials, customer PII, or actual customer configs
— sanitize or fake the data first.
