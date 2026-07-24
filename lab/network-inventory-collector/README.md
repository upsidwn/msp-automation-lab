# Network Inventory Collector

Status: working against Juniper, Extreme EXOS, and UniFi — connects,
pulls version/hardware/interfaces, writes JSON + CSV to `output/`. The
interactive `run.py` loop handles the SSH vendors (Juniper/EXOS) in one
run off a shared credential pool; UniFi is a separate standalone
collector (`collect_unifi.py`) since it works fundamentally differently
— see Scope below. Lives in `lab/` until it's stable enough to move to
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
  - **SSH via Netmiko** for Junos and EXOS — one connection per device,
    `device_type: juniper_junos` / `extreme_exos`, driven by `run.py`'s
    per-device loop.
  - **UniFi Network Integration API** (official, key-based auth — not
    the older unofficial controller API) for the Ubiquiti gear. One
    call to the console returns *every* adopted device at once, so this
    doesn't fit the per-device SSH loop at all — it's a standalone
    script (`collect_unifi.py`). No SSH to individual APs/switches:
    they're controller-managed, and this API is the officially
    supported way in.
- Build/test order: Juniper first (lowest risk), then Extreme (virtual
  lab instance), then UniFi (different code path entirely) — all three done.

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
- **UniFi confirmed live** — key-based auth against the real console,
  all adopted devices (AP/switch/gateway) collected in one call. No
  serial number available from this API (field doesn't exist), so
  `serial` is `null` for UniFi devices and MAC address is kept instead
  as the stable identifier. Interface detail is coarse compared to
  Junos/EXOS — see design-notes.md.

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
- `source/config.py` — env-var host + credential pool + UniFi API key loading
- `source/auth.py` — shared credential-pool connect logic (pool → prompt fallback), SSH vendors only
- `source/collector.py` — Junos JSON parsing (version/hardware/interfaces)
- `source/collector_exos.py` — Extreme EXOS text parsing (version/switch/ports/vlan)
- `source/collector_unifi.py` — UniFi Integration API calls + record building
- `source/collect.py` — single-device Juniper CLI: connect → parse → write JSON/CSV
- `source/collect_unifi.py` — standalone UniFi CLI: one API key → every device → write JSON
- `source/run.py` — interactive multi-device/multi-vendor loop (Juniper/EXOS), shared pool, combined output
- `tests/fixtures/*` — sanitized fixtures (fake serials/models/IPs/MACs, real format), used by the parser tests

## Notes

Read-only creds only, never hardcoded — see [docs/NOTES.md](../../docs/NOTES.md).

Config backup (copying/versioning device configs) is a related but
separate idea, already tracked in [docs/ROADMAP.md](../../docs/ROADMAP.md)'s
backlog — not part of this collector, but the connection/credential
pattern here should carry over directly when that project starts.

See [docs/ROADMAP.md](../../docs/ROADMAP.md) (Phase 2) for the bigger
picture.
