# Network Inventory Collector

Status: working against Juniper, Extreme EXOS, and UniFi. Connects,
pulls version/hardware/interfaces, writes JSON + CSV to `output/`. The
interactive `run.py` loop handles the SSH vendors (Juniper/EXOS) in one
run off a shared credential pool; UniFi is a separate standalone
collector (`collect_unifi.py`) since it works fundamentally differently
(see Scope below). Lives in `lab/` until it's stable enough to move to
`production/`.

## Quick start

```
pip install -r source/requirements.txt
cp .env.example .env   # then fill in real values
python source/menu.py
```

Prints a numbered list of every tool below, explains what it needs
right before running it, and hands off to it. Any script in `source/`
also runs fine on its own without the menu, e.g. `python
source/discover.py 192.168.1.0/24`.

1. **Auto-discover a subnet**, nmap scan of a whole CIDR (auto-detects
   your local one, or type a different one), tries anything with SSH
   open against your credential pool and sends UniFi controllers
   through the API path instead. Point it at a network and see what's
   on it. Needs `nmap` installed (`brew install nmap` on macOS).
2. **Scan for Extreme EXOS devices only**, same scan as above, filtered
   down to just EXOS afterward.
3. **Manual multi-device collection**, type a vendor and IP in one at
   a time, or point it at a CSV list (`vendor,host` per line) if you
   already have one.
4. **Single Juniper device**, a quick one-off pull from one Junos box.
5. **UniFi controller**, pulls every adopted device from a console in
   one API call.
6. **Firmware inventory report**, no new scan, reads whatever's
   already in `output/`, flags each device compliant/outdated against
   `known_good_firmware.json`. Asks before saving to a file.

Options 3-5 will ask whether to use `.env` or let you type a host/API
key/credentials in on the spot instead.

## What it does

Connects to network devices and pulls together a standard inventory
report: hostname, vendor, model, serial, firmware, interfaces, IPs.
Basically automating the "log into every device and write down what it
is" step.

## Scope for v1

- Static list of devices to start, no auto-discovery yet
- Output: CSV and/or JSON
- Two collection paths, since the gear doesn't all speak the same language:
  - **SSH via Netmiko** for Junos and EXOS, one connection per device,
    `device_type: juniper_junos` / `extreme_exos`, driven by `run.py`'s
    per-device loop.
  - **UniFi Network Integration API** (official, key-based auth, not
    the older unofficial controller API) for the Ubiquiti gear. One
    call to the console returns *every* adopted device at once, so this
    doesn't fit the per-device SSH loop at all; it's a standalone
    script (`collect_unifi.py`). No SSH to individual APs/switches:
    they're controller-managed, and this API is the officially
    supported way in.
- Build/test order: Juniper first (lowest risk), then Extreme (virtual
  lab instance), then UniFi (different code path entirely). All three done.

## Confirmed

- **Python + Netmiko** over Ansible, working end to end against both
  Juniper and Extreme EXOS.
- **Data schema**: hostname, vendor, model, firmware, serial, interfaces
  (name/admin_status/oper_status/ip_addresses), same shape for every
  vendor. See [design-notes.md](documentation/design-notes.md) for exact
  field sources and per-vendor parsing quirks.
- **Output**: full JSON record + a flattened one-row CSV summary
  (single-device path), or one combined JSON array for a multi-device
  `run.py` session, all written to `output/`.
- **Multi-vendor auth confirmed**: the credential pool is shared across
  vendors in a single `run.py` session (not just per-device); a
  credential learned on one device is tried against the next regardless
  of vendor.
- **UniFi confirmed live**: key-based auth against the real console,
  all adopted devices (AP/switch/gateway) collected in one call. No
  serial number available from this API (field doesn't exist), so
  `serial` is `null` for UniFi devices and MAC address is kept instead
  as the stable identifier. Interface detail is coarse compared to
  Junos/EXOS (see design-notes.md).

## Still deciding

- Where the device list comes from for something bigger than manual
  prompting (probably a YAML file, or the eventual auto-discovery piece)
- Whether output feeds a NetBox import later or just stands alone

## Auth

Credentials are a pool, not one fixed set. Real networks rarely have a
single account that works everywhere. `connect_with_pool()` tries each
known credential in order; if none work, it prompts interactively and
keeps the working one in memory for the rest of that run (never written
back to disk). See `source/auth.py` and `source/config.py`.

## Source layout

- `source/connect_test.py`: raw SSH smoke test (Juniper only, connect + print `show version`)
- `source/config.py`: env-var host + credential pool + UniFi API key loading
- `source/auth.py`: shared credential-pool connect logic (pool → prompt fallback), SSH vendors only
- `source/collector.py`: Junos JSON parsing (version/hardware/interfaces)
- `source/collector_exos.py`: Extreme EXOS text parsing (version/switch/ports/vlan)
- `source/collector_unifi.py`: UniFi Integration API calls + record building
- `source/collect.py`: single-device Juniper CLI: connect → parse → write JSON/CSV
- `source/collect_unifi.py`: standalone UniFi CLI: one API key → every device → write JSON
- `source/run.py`: multi-device/multi-vendor collection (Juniper/EXOS), shared pool, combined output. Type devices in one at a time, or pass `--devices-file` with a vendor,host CSV to skip the prompting
- `source/menu.py`: single entry point, lists every tool above and runs whichever one you pick as a subprocess
- `source/nmap_scan.py`: runs nmap (plain TCP connect scan, no sudo needed), parses XML into candidate hosts
- `source/discover.py`: auto-discovery entry point: scan a CIDR (or auto-detect the local one), dispatch each candidate to the right collector, write combined output
- `source/subnet_detect.py`: figures out the local machine's own subnet, for when discover.py isn't given an explicit CIDR
- `source/arp_lookup.py`: reads a host's MAC from the OS's own ARP cache, no elevated privileges needed
- `source/oui_lookup.py`: MAC → manufacturer lookup (IEEE OUI registry via `mac-vendor-lookup`)
- `source/firmware_report.py`: no new scan, reads every `output/*.json` from previous runs, checks compliance against `known_good_firmware.json`, asks before saving to a file
- `known_good_firmware.json`: acceptable firmware versions per vendor, edit for your environment
- `.env.example`: every env var the tools read, copy to `.env` and fill in real values
- `tests/fixtures/*`: sanitized fixtures (fake serials/models/IPs/MACs, real format), used by the parser tests

## System requirements

Beyond the Python packages in `requirements.txt`, `nmap` must be
installed separately (it's a CLI tool, not a pip package). On macOS:
`brew install nmap`.

## Notes

Read-only creds only, never hardcoded (see [docs/NOTES.md](../../docs/NOTES.md)).

Config backup (copying/versioning device configs) is a related but
separate idea, already tracked in [docs/ROADMAP.md](../../docs/ROADMAP.md)'s
backlog. Not part of this collector, but the connection/credential
pattern here should carry over directly when that project starts.

See [docs/ROADMAP.md](../../docs/ROADMAP.md) (Phase 2) for the bigger
picture.
