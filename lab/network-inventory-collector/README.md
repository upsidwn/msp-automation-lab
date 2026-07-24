# Network Inventory Collector

Status: working v1 against the Juniper switch — connects, pulls
version/hardware/interfaces, writes JSON + CSV to `examples/`. Lives in
`lab/` until it's stable enough to move to `production/`.

## What it does

Connects to network devices and pulls together a standard inventory
report — hostname, vendor, model, serial, firmware, interfaces, IPs.
Basically automating the "log into every device and write down what it
is" step.

## Lab gear

- Juniper switch, Junos, vanilla/no real config — safest to break, build here first
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
- Build/test order: Juniper first (lowest risk), then Extreme, then the
  UniFi API integration last (different code path entirely)

## Confirmed

- **Python + Netmiko** over Ansible — working end to end against the
  Juniper switch.
- **Data schema** — hostname, vendor, model, firmware, serial, interfaces
  (name/admin_status/oper_status/ip_addresses). See
  [design-notes.md](documentation/design-notes.md) for exact field
  sources and JSON parsing quirks.
- **Output** — full JSON record + a flattened one-row CSV summary, both
  written to `examples/`.

## Still deciding

- Where the device list comes from once there's more than one box
  (probably a YAML file — not needed yet with a single device)
- Whether output feeds a NetBox import later or just stands alone

## Source layout

- `source/connect_test.py` — raw SSH smoke test (connect, print `show version`)
- `source/config.py` — env-var credential loading
- `source/collector.py` — Junos JSON parsing (version/hardware/interfaces)
- `source/collect.py` — the real collector: connect → parse → write JSON/CSV
- `tests/fixtures/*.json` — real captures from the lab switch, used by the parser tests

## Notes

Read-only creds only, never hardcoded — see [docs/NOTES.md](../../docs/NOTES.md).

Config backup (copying/versioning device configs) is a related but
separate idea, already tracked in [docs/ROADMAP.md](../../docs/ROADMAP.md)'s
backlog — not part of this collector, but the connection/credential
pattern here should carry over directly when that project starts.

See [docs/ROADMAP.md](../../docs/ROADMAP.md) (Phase 2) for the bigger
picture.
