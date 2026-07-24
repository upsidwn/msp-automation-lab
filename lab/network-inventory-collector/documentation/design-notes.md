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

## UniFi Integration API notes

Uses the official **Network Integration API** (`/proxy/network/integration/v1/...`
on the console itself), not the older unofficial controller API, and not
Ubiquiti's cloud API (`api.ui.com`) -- staying local keeps this
consistent with the SSH collectors (no cloud dependency, nothing leaves
the customer's network). Auth is a static API key generated from the
console's own UI, sent as an `X-API-KEY` header -- confirmed live, first
try. No username/password, no session cookies, and critically no
interaction with cloud-account 2FA at all, since it's a separate
credential mechanism entirely.

Flow: `GET /sites` -> site `id` -> `GET /sites/{id}/devices` -> every
adopted device (AP/switch/gateway) in one response. Confirmed fields:
`id`, `macAddress`, `ipAddress`, `name`, `model`, `state`
(`ONLINE`/`OFFLINE`), `firmwareVersion`, `features`, `interfaces`. The
detail endpoint (`/sites/{id}/devices/{deviceId}`) adds `provisionedAt`,
`configurationId`, `uplink` -- no serial number anywhere in this API, at
any endpoint. `serial` is `null` for UniFi records; `mac_address` is
kept as an extra field since it's the only stable per-device identifier
this API gives us.

`interfaces` in the raw API response is just a capability tag (e.g.
`["radios"]` or `["ports"]`), not per-port/per-radio link state like
Junos/EXOS provide -- this API tier is scoped to "what exists and is it
online," not granular port telemetry. Each device gets one synthetic
`mgmt` interface entry carrying its own IP, with `admin_status`/
`oper_status` derived from `state`. Getting real per-port detail would
need a different/deeper endpoint, not explored yet -- noted as a known
v1 limitation, not a bug.

Architecturally different from the SSH collectors: one API call returns
*every* device, instead of one connection per device. Doesn't fit
`run.py`'s per-device loop at all, so it's a standalone script
(`collect_unifi.py`) rather than another entry in `run.py`'s `VENDORS`
registry. This is actually closer to the eventual auto-discovery goal
than the SSH loop is -- no per-device IP prompting needed.

Fixtures in `tests/fixtures/unifi_*.json` are hand-written to match the
real response shape, with fake IDs/MACs/IPs/names throughout.

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

## nmap-based discovery (planned)

Auto-discovery scoped deliberately narrower than the full "moderate vs.
thorough" tradeoff space discussed in the roadmap -- one clean, testable
slice rather than trying to build the whole thing at once. Leans on
mature existing tools (nmap, later SNMP/`lldpd`) rather than hand-rolled
scanning, both for reliability and because reimplementing what nmap
already does well isn't a good use of time.

**v1 scope:**

1. **Target**: explicit CIDR passed in, not auto-detected yet.
   Subnet auto-detection is its own small problem (multiple interfaces,
   VPNs, etc.) -- fast-follow, not bundled into the first pass.
2. **Scan**: `nmap -sT -sV --open -p 22,80,443 <cidr> -oX -` -- plain
   TCP connect scan (no `-sS`/`-O`, so no `sudo` required), service/
   version detection on just the ports that matter here, XML output
   piped to Python instead of screen-scraping text.
3. **Parse**: stdlib `xml.etree.ElementTree` (no new dependency) turns
   nmap's XML into candidates: `{ip, mac, open_ports, service_banners}`.
4. **Dispatch**: candidates with port 22 open get tried against the
   credential pool using each supported `device_type` in turn
   (`juniper_junos`, `extreme_exos`) via the existing
   `auth.connect_with_pool()` -- no new auth machinery. Candidates with
   443 open get tried against the UniFi Integration API path.
5. **Output**: same record schema, same `output/` write pattern as
   everything else. Anything nmap found but couldn't classify/
   authenticate still shows up as an "unidentified" entry -- nothing
   silently dropped.
6. **New files**: `nmap_scan.py` (run nmap, parse XML, return
   candidates -- testable in isolation) and `discover.py` (orchestrator:
   scan -> dispatch -> collect -> write). Same separation of concerns
   as the rest of the project: "run an external tool" stays separate
   from "decide what to do with results."
7. **Testing**: nmap itself can't be unit tested, but XML parsing can --
   same fixture pattern as everywhere else (hand-sanitized fake nmap
   XML output, not a real capture).

**Explicitly deferred** to later work: subnet auto-detection, SNMP
`sysDescr` sweep, `lldpd`-based passive seed discovery (zero-credential
"what's my upstream switch" bootstrap), multi-VLAN traversal. These are
real Tier B/C items from the roadmap discussion, not abandoned -- just
sequenced after a working v1 exists.

## Next up

- nmap-based discovery, scoped above -- the next concrete piece of work.
- Multi-device loop already exists (`run.py`) for the SSH vendors; a
  real device *list* (`devices.yml` or similar) may end up superseded
  by discovery itself rather than being a separate precursor step.
- UniFi per-port/per-radio detail, if a deeper API endpoint exists for it.
- All three vendors (Junos, EXOS, UniFi) now have working collectors --
  discovery is what ties them together into the actual end-goal flow.
