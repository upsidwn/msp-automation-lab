# Network Inventory Collector

Status: working against both Juniper and Extreme EXOS — connects, pulls
version/hardware/interfaces, writes JSON + CSV to `output/`. The
interactive `run.py` loop handles both vendors in one run off a shared
credential pool. Lives in `lab/` until it's stable enough to move to
`production/`.

## What it does

Connects to network devices and pulls together a standard inventory
report — hostname, vendor, model, serial, firmware, interfaces, IPs.
Basically automating the "log into every device and write down what it
is" step.

## Lab gear

- Juniper switch, Junos, vanilla/no real config — safest to break, build here first
- Extreme EXOS, virtual lab instance (EVE-NG or similar)
- Ubiquiti, UniFi controller-managed (UDM/Cloud Key)

## Scope for v1

- Static list of devices to start — no auto-discovery yet
- Output: CSV and/or JSON
- Two collection paths, since the gear doesn't all speak the same language:
  - **SSH via Netmiko** for Junos and EXOS — `device_type: juniper_junos` /
    `extreme_exos`
  - **UniFi Network controller API** for the Ubiquiti gear — it's
    controller-managed, so SSH to individual devices isn't the normal
    path; pull inventory from the controller's local REST API instead.
    This will end up as a separate module from the SSH collector.
- Build/test order: Juniper first (lowest risk), then Extreme (virtual
  lab instance), then the UniFi API integration last (different code
  path entirely)

## Confirmed

- **Python + Netmiko** over Ansible — working end to end against both
  Juniper and Extreme EXOS.
- **Data schema** — hostname, vendor, model, firmware, serial, interfaces
  (name/admin_status/oper_status/ip_addresses), same shape for every
  vendor. See [design-notes.md](documentation/design-notes.md) for exact
  field sources and per-vendor parsing quirks.
- **Output** — full JSON record + a flattened one-row CSV summary
  (single-device path), or one combined JSON array for a multi-device
  `run.py` session — all written to `output/`.
- **Multi-vendor auth confirmed** — the credential pool is shared across
  vendors in a single `run.py` session (not just per-device); a
  credential learned on one device is tried against the next regardless
  of vendor.

## Still deciding

- Where the device list comes from for something bigger than manual
  prompting (probably a YAML file, or the eventual auto-discovery piece)
- Whether output feeds a NetBox import later or just stands alone

## Auth

Credentials are a pool, not one fixed set — real networks rarely have a
single account that works everywhere. `connect_with_pool()` tries each
known credential in order; if none work, it prompts interactively and
keeps the working one in memory for the rest of that run (never written
back to disk). See `source/auth.py` and `source/config.py`.

## Source layout

- `source/connect_test.py` — raw SSH smoke test (Juniper only, connect + print `show version`)
- `source/config.py` — env-var host + credential pool loading
- `source/auth.py` — shared credential-pool connect logic (pool → prompt fallback)
- `source/collector.py` — Junos JSON parsing (version/hardware/interfaces)
- `source/collector_exos.py` — Extreme EXOS text parsing (version/switch/ports/vlan)
- `source/collect.py` — single-device Juniper CLI: connect → parse → write JSON/CSV
- `source/run.py` — interactive multi-device/multi-vendor loop, shared pool, combined output
- `tests/fixtures/*` — sanitized fixtures (fake serials/models/IPs, real format), used by the parser tests

## Notes

Read-only creds only, never hardcoded — see [docs/NOTES.md](../../docs/NOTES.md).

Config backup (copying/versioning device configs) is a related but
separate idea, already tracked in [docs/ROADMAP.md](../../docs/ROADMAP.md)'s
backlog — not part of this collector, but the connection/credential
pattern here should carry over directly when that project starts.

See [docs/ROADMAP.md](../../docs/ROADMAP.md) (Phase 2) for the bigger
picture.
