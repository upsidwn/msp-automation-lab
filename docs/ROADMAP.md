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

- ~~Auto-discovery for the inventory collector~~ done — nmap + mDNS +
  optional ARP sweep, CIDR-scoped, live progress table, see
  `lab/network-inventory-collector/documentation/design-notes.md`. Full
  SNMP/LLDP/multi-VLAN vision deliberately deferred.
- ~~Ansible dynamic inventory bridge~~ done, `dynamic_inventory.py`:
  reads discover.py's output, exposes it as Ansible's `--list` JSON
  contract grouped by vendor (junos/exos), opt-in alongside the static
  hosts.yml (`ansible-playbook backup.yml -i dynamic_inventory.py`).
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
- ~~Containerized dev environment~~ done, `Dockerfile` +
  `docker-build-collector` CI job for network-inventory-collector.
- Infra monitoring dashboard
- Credential management examples (vault, secret managers)

Future tech to poke at: NetBox, RAG, local LLMs.

---

## Next up: platform/IaC track

Decided order, each step builds on the last:

1. **Terraform for Proxmox** — replace manual VM creation on the NUC
   with `.tf` files (`bpg/proxmox` provider), real plan/apply/state
   workflow.
2. **Kubernetes (k3s)** — deploy the collector as a real CronJob
   (Secret for creds, PersistentVolume for `output/`) instead of a
   generic hello-world pod. Terraform provisions the VM(s) it runs on.
3. **CD** — CI already builds the image; push it to GHCR on merge,
   Argo CD or Flux watches the cluster and auto-deploys new tags.
   GitOps, not just CI.
4. **Cloud** — last on purpose, costs money if left running and the
   Terraform skill transfers directly once learned locally. First real
   tie-in: give config-backup-system an actual off-site destination
   (S3 via Terraform) instead of local-disk-only backups.

---

## Notes to self

- Document before building — figure out scope before writing code.
- Small PRs beat big ones.
- Quality over quantity — finish things instead of piling up half-started
  experiments.
