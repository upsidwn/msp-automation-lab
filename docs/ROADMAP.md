# Roadmap

MSP Automation Lab — a portfolio/learning project exploring automation, IaC,
and AI-assisted workflows for MSP operations. Not trying to replace
technicians, just cut the repetitive stuff so there's more time for the
problems that actually need a person.

Also doubles as a way for me to practice real engineering workflows
(branches, PRs, docs-first, eventually CI/CD) instead of just writing
one-off scripts.

---

## Phases

**Phase 1 — Foundation** (mostly done)
Repo structure, docs, dev standards, GitHub setup.

**Phase 2 — Infrastructure Automation** (in progress)
Network inventory collection, config backups, firmware/health checks.
Ansible + Python + SSH/REST APIs.
→ Currently building: [`lab/network-inventory-collector/`](../lab/network-inventory-collector/README.md)
→ Endgame for the collector: point it at a network (e.g. a NUC/laptop
dropped on a customer LAN) and have it auto-discover and inventory
devices on its own, instead of being handed one IP/vendor at a time —
see the backlog item below.

**Phase 3 — Documentation Automation** (planned)
Turn technician notes into structured docs / KB drafts automatically.

**Phase 4 — AI-Assisted Workflows** (planned)
Ticket summarization, troubleshooting help, doc generation. AI assists,
doesn't decide.

**Phase 5 — Workflow Automation / Integrations** (planned)
Wire ticketing + monitoring + AI together into actual end-to-end workflows.

**Phase 6 — Monitoring & Reporting** (future, loosely planned)
Dashboards, compliance checks, metrics. Grafana/Prometheus probably.

---

## Backlog / other ideas

Not committed to building all of these — just parked here so I don't
forget them:

- **Auto-discovery for the inventory collector** (in progress) — all
  three vendor collectors (Junos, EXOS, UniFi) now exist, so this is the
  active next piece. v1 leans on nmap (host/port/service discovery) +
  the existing credential pool for dispatch, deliberately scoped
  narrower than the full SNMP/LLDP/multi-VLAN vision — see
  `lab/network-inventory-collector/documentation/design-notes.md` for
  the actual plan and what's deferred to later passes.
- **Ansible dynamic inventory bridge** — once the collector/discovery
  tooling produces a real device list, expose it as an Ansible dynamic
  inventory source (a script implementing Ansible's `--list` JSON
  contract). Lets downstream config-management work (e.g. the
  Configuration Backup System idea below) consume discovered devices
  directly instead of duplicating inventory logic. Better fit for
  Ansible here than trying to use it for discovery itself — Ansible
  wants a known inventory to act on, not to go find unknown things.
- ~~Firmware compliance reporter~~ done, `firmware_report.py`
- ~~Device diagram generator~~ done, `diagram.py` (inventory diagram,
  not real topology, see below)
- Real network topology mapping (LLDP neighbor data), new collector
  capability needed first, not a diagram tweak
- Customer environment doc generator
- Customer onboarding automation
- Automated customer health reports
- Ticket workflow automation (n8n?)
- AI knowledge base generator
- AI-assisted change documentation
- Internal MSP AI assistant (RAG over internal docs)
- ~~CI/CD pipeline (markdown/python/ansible lint + security scanning)~~
  done, `.github/workflows/ci.yml`: pytest for both lab projects, ruff,
  yamllint, ansible-lint, gitleaks. Markdown lint deferred, everything
  else in v1.
- Containerized dev environment
- Infra monitoring dashboard
- Credential management examples (vault, secret managers)

Future tech to poke at: Kubernetes, NetBox, RAG, local LLMs.

---

## Notes to self

- Document before building — figure out scope before writing code.
- Small PRs beat big ones.
- Quality over quantity — finish things instead of piling up half-started
  experiments.
