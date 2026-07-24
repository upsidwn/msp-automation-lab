# Design notes

## Data schema (confirmed against the real EX4300)

```json
{
  "hostname": null,
  "vendor": "juniper",
  "model": "ex4300-48p",
  "firmware": "21.4R3.15",
  "serial": "PD3716420189",
  "interfaces": [
    {"name": "irb", "admin_status": "up", "oper_status": "up", "ip_addresses": ["172.30.10.212/24"]}
  ],
  "collected_at": "2026-07-24T15:42:25Z"
}
```

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

Test fixtures in `tests/fixtures/*.json` are real captures from the lab
switch, not synthetic -- parser tests run against actual device output.

## Decisions log

- **Python + Netmiko**, not Ansible -- confirmed working for Junos.
- **Two collection scripts**: `connect_test.py` (raw SSH smoke test) and
  `collect.py` (the real parser + JSON/CSV output to `examples/`).
- **Output**: full JSON record with nested interfaces, plus a flattened
  one-line-per-device CSV summary (hostname/vendor/model/serial/firmware/
  interface count) for quick spreadsheet use.
- **Config backup** (copying/versioning device configs) is a related but
  separate idea already tracked in the roadmap backlog -- not part of this
  collector. The same Netmiko connection + env-based credential pattern
  built here should carry over directly when that project starts.

## Next up

- Extreme EXOS support (`device_type: extreme_exos`) -- same pattern,
  different command set and parser, once that switch is racked.
- Multi-device loop (`devices.yml`) once there's more than one Junos box
  to hit.
