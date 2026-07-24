# Design notes

## Data schema (confirmed against the Juniper lab switch)

```json
{
  "hostname": null,
  "vendor": "juniper",
  "model": "lab-switch-1",
  "firmware": "21.4R3.15",
  "serial": "lab-switch-1-serial",
  "interfaces": [
    {"name": "irb", "admin_status": "up", "oper_status": "up", "ip_addresses": ["192.0.2.212/24"]}
  ],
  "collected_at": "2026-07-24T15:42:25Z"
}
```

(Model/serial/IP above are sanitized placeholders, not real values — real
collector output never gets committed, see `.gitignore` and the note in
[docs/NOTES.md](../../../docs/NOTES.md).)

`hostname` comes back `null` on this switch since it's vanilla/unconfigured
-- Junos only reports it if `set system host-name` has been set. Not a bug,
just means an unconfigured device won't have one.

## Junos JSON parsing notes

Junos wraps every leaf value as `[{"data": ...}]` -- see `_first_data()` in
`source/collector.py`. Confirmed key paths (via a real `show ... | display
json` against the lab switch):

- Model/firmware: `multi-routing-engine-results[0].multi-routing-engine-item[0].software-information[0]`
- Serial: `chassis-inventory[0].chassis[0].serial-number[0].data`
- Interface IPs: `interface-information[0].physical-interface[].logical-interface[].address-family[].interface-address[].ifa-local[0].data`

Test fixtures in `tests/fixtures/*.json` match the real device's structure
and format, but every identifying value (serial, model, IP) is a
hand-written fake -- not a real capture. Parser tests run against that
sanitized structure, which is enough to exercise the real parsing logic
without ever storing real device data.

## Extreme EXOS parsing notes

EXOS has no JSON pipe like Junos's `| display json` -- `collector_exos.py`
regex-parses plain CLI text from four commands instead:

- `show version` -- `Switch : <part#> <serial> Rev <rev> ... IMG: <firmware>`
  line gives serial + firmware.
- `show switch` -- `SysName:` / `System Type:` give hostname/model as
  simple `label: value` lines.
- `show ports info detail` -- one block per port (`Port:`, `Admin
  state:`, `Link State:`, plus VLAN/STP config we don't need). Admin
  state (`Enabled`/`Disabled`) and Link State (`Active`/`Ready`) are
  genuinely independent fields here, so `admin_status`/`oper_status` are
  no longer forced to mirror each other like the earlier
  `show ports information` table-based approach. Confirmed live: a
  disconnected-but-enabled port shows up/down, a connected port shows
  up/up. Full output for 56 ports came back in one shot with no
  pagination handling needed -- Netmiko already disables paging for this
  platform.
- `show vlan` -- EXOS assigns IPs to VLANs, not physical ports. Each
  VLAN with an IP becomes its own `vlan-<name>` entry in `interfaces`,
  the same way Junos's `irb` interface carries the switch's own IP.

Fixtures in `tests/fixtures/exos_*.txt` are hand-written to match this
format exactly, with fake values throughout.

## Decisions log

- **Python + Netmiko**, not Ansible -- confirmed working for both Junos
  and EXOS.
- **Per-vendor parser modules** (`collector.py` for Junos,
  `collector_exos.py` for EXOS) sharing one `collect(conn, host)` shape,
  so `run.py` can dispatch to either without caring which vendor it's
  talking to.
- **Two entry points**: `collect.py` (single-device Juniper CLI) and
  `run.py` (interactive multi-device/multi-vendor loop with a shared
  credential pool). `connect_test.py` stays as the raw Juniper smoke test.
- **Output**: full JSON record with nested interfaces, plus either a
  flattened one-line CSV summary (single-device) or one combined JSON
  array (multi-device run), written to `output/`.
- **Config backup** (copying/versioning device configs) is a related but
  separate idea already tracked in the roadmap backlog -- not part of this
  collector. The same Netmiko connection + env-based credential pattern
  built here should carry over directly when that project starts.

## Next up

- Multi-device loop already exists (`run.py`); next is a real device
  *list* (`devices.yml` or similar) instead of prompting for one IP at a
  time -- precursor to real auto-discovery.
- UniFi controller API integration (separate code path, not SSH-based).
