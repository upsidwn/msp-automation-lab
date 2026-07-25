# Notes

Working notes and standards for this repo: security, tooling, project
conventions. Not gospel, just what I want to keep consistent as this
grows.

---

## Project structure

Each automation project gets its own folder:

```
project-name/
  README.md
  documentation/
  source/
  output/
  tests/
```

---

## Security

- Never hardcode creds. Env vars or Ansible Vault.
- Read-only accounts for anything that just collects info.
- Don't log passwords/tokens/API keys.
- Don't store customer PII unless there's a real reason to, and encrypt it
  if you do.
- Real collector output never gets committed. Serials, hostnames, IPs,
  model numbers, etc. from actual gear stay local (`output/*.json`/
  `*.csv` are gitignored). Test fixtures are sanitized/fake data, not
  real captures, every identifying field (serial, model, IP), not just
  serial/IP, so the test suite still runs for anyone without the actual
  hardware.
- Keep personal lab gear descriptions generic in anything committed:
  vendor and general type only, not exact model numbers or serials.
- Don't persist prompted/discovered device creds to disk in plaintext.
  In-memory for the run is fine, use an OS keychain (e.g. `keyring`) if
  persistence across runs is ever needed, not a growing `.env`.
- Before every commit: `git diff` / `git status`, check nothing sensitive
  snuck in.
- If a secret leaks into a commit anyway: rotate it immediately, assume
  it's burned.

---

## Automation principles

- Idempotent where possible, running it twice shouldn't double the
  damage.
- Automate the boring/repetitive stuff, not the judgment calls.
- Fail loudly, not silently, log what happened, what failed, why.
- Test the unhappy path too (bad creds, unreachable device, timeouts),
  not just the demo path.

---

## Tech stack (and why)

- **Python**: most automation logic, API integrations, glue code
- **Ansible**: network device automation, config management (agentless)
- **Bash**: quick scripts, environment setup
- **Docker**: local dev, running supporting services
- **Terraform**: IaC, mostly for later cloud stuff
- **Git/GitHub**: version control, issues, PRs
