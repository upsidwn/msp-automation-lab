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

- Firmware compliance reporter
- Network diagram generator
- Customer environment doc generator
- Customer onboarding automation
- Automated customer health reports
- Ticket workflow automation (n8n?)
- AI knowledge base generator
- AI-assisted change documentation
- Internal MSP AI assistant (RAG over internal docs)
- CI/CD pipeline (markdown/python/ansible lint + security scanning)
- Containerized dev environment
- Infra monitoring dashboard
- Credential management examples (vault, secret managers)

Future tech to poke at: Kubernetes, NetBox, RAG, local LLMs, GitHub Actions.

---

## Notes to self

- Document before building — figure out scope before writing code.
- Small PRs beat big ones.
- Quality over quantity — finish things instead of piling up half-started
  experiments.
