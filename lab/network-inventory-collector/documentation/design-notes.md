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

## nmap-based discovery (v1 done)

Auto-discovery scoped deliberately narrower than the full "moderate vs.
thorough" tradeoff space discussed in the roadmap -- one clean, testable
slice rather than trying to build the whole thing at once. Leans on
mature existing tools (nmap, `arp`, IEEE's OUI registry) rather than
hand-rolled scanning, both for reliability and because reimplementing
what these already do well isn't a good use of time.

**What shipped:**

1. **Target**: explicit CIDR passed as a CLI arg (`python discover.py
   <cidr>`), not auto-detected yet.
2. **Scan**: `nmap -sT -sV --open -p 22,80,443 <cidr> -oX -` -- plain
   TCP connect scan (no `-sS`/`-O`, so no `sudo` required), XML parsed
   via stdlib `xml.etree.ElementTree` into `{ip, mac, ports}` candidates
   (`nmap_scan.py`, tested in isolation with an inline XML sample rather
   than a fixture file -- unlike vendor hardware, anyone running this
   has a network to test against, so there's nothing real-world to
   sanitize).
   - **Discovery-probe fix, confirmed live against a real `/24`**: a
     real, reachable device (SSH open, directly reachable in isolation)
     got silently skipped by nmap's *default* host-discovery probes
     (ICMP + a couple of fixed ports) -- not a timing/speed problem, a
     wrong-probe-type problem. `-Pn` (skip discovery, port-scan every
     IP directly) fixed it but at real cost: one slow-responding host
     alone added 190+ seconds to the scan. The actual fix was using SYN
     probes against our *own* target ports for discovery
     (`-PS22,80,443`) instead of nmap's defaults -- found the missing
     device *and* found more live hosts overall (14 vs. 6), landing
     around 90-120s for a full `/24`, in line with what's acceptable
     for a real site visit. `--host-timeout 90s` caps how long any
     single host can eat into the scan. Full `-Pn` stays available as
     an explicit `--thorough` opt-in for a deliberate final pass, not
     the routine default.
   - **Live progress**: `--stats-every 10s` streamed via a background
     thread reading nmap's stderr in real time (`_stream_progress()`),
     rather than us reimplementing per-host progress tracking nmap
     already does -- good enough for a terminal-driven tool; the
     eventual production form of this won't be terminal-driven anyway.
3. **Dispatch**: candidates with port 22 open get tried against
   `auth.try_ssh_device_types()` -- a *non-prompting* variant of the
   pool logic, built specifically for discovery, where the vendor isn't
   known yet. A wrong device_type guess against a real device doesn't
   always fail the same way -- confirmed live it can raise
   `NetmikoAuthenticationException`, `NetmikoTimeoutException`, *or*
   `netmiko.exceptions.ReadTimeout` (a session-prep pattern mismatch --
   this one crashed the first live test run since it isn't a subclass
   of the other two; Netmiko's exceptions split across two unrelated
   root classes, `SSHException` and `NetmikoBaseException`, so both are
   caught now). Candidates with 443 open get tried against the UniFi
   Integration API.
4. **MAC + manufacturer enrichment** for anything that couldn't be
   identified -- the case where this adds the most value, since an
   identified Junos/EXOS/UniFi record already names its own vendor.
   Considered `tshark` for passive ARP sniffing, but that (like
   `lldpd`, like nmap's own `-O`) needs raw packet capture / elevated
   privileges. Turned out unnecessary: reading the IP the same way
   nmap already talked to it means the OS kernel already resolved the
   MAC during that connection and cached it -- `arp -n <ip>`
   (`arp_lookup.py`) reads that cache with **zero elevated privileges**,
   confirmed live. Only works for hosts on the same local subnet as the
   scanning box (routed traffic never reveals the far end's real MAC,
   regardless of privilege level) -- which is exactly the use case that
   matters here. Feeds into `oui_lookup.py` (the `mac-vendor-lookup`
   package -- downloads/caches the IEEE OUI registry locally on first
   use, works offline after that; worth knowing for a fully air-gapped
   deployment, not a blocker otherwise). Confirmed live: an
   unidentifiable host got flagged "possibly Raspberry Pi Trading Ltd"
   -- genuinely useful field intel that wasn't available before.
5. **Output**: same record schema, same `output/` write pattern as
   everything else -- `{"records": [...], "unidentified": [...]}`.
   Nothing nmap found gets silently dropped.
6. **New files**: `nmap_scan.py`, `discover.py`, `arp_lookup.py`,
   `oui_lookup.py`. Same separation of concerns as the rest of the
   project -- "run an external tool" stays separate from "decide what
   to do with results."

**Explicitly deferred** to later work: subnet auto-detection, SNMP
`sysDescr` sweep, multi-VLAN traversal, and the whole "does this tool
embrace running as root" question (raised again by `-O`/`-sS` and
`tshark`, on top of `lldpd` from earlier -- worth deciding once,
deliberately, rather than piecemeal; the tool's actual deployment target
being a dedicated appliance rather than someone's daily-driver laptop
makes that a smaller concern than it first sounds). Real Tier B/C items
from the roadmap discussion, not abandoned -- just sequenced after a
working v1 exists.

## Privilege model decision

Decided: opt-in elevated mode, per-tool, not blanket-sudo-at-startup.

The collector stays unprivileged by default (current `-sT` + `-PS` +
`arp -n` approach needs no root at all). When a feature that genuinely
needs elevated privileges gets built -- `tshark` (passive ARP capture),
`lldpd` (LLDP neighbor discovery), nmap `-O`/`-sS` (OS detection / SYN
scan) -- it prompts for sudo at the moment it's about to run that
specific operation, explains what it's for and why, and elevates only
that one call. Not "ask once at launch, run the whole program as root
from then on."

A session-level "allow sudo for everything" override is fine as a
convenience for repeat runs, but per-tool prompting is the default,
not the fallback. Same shape as how this app itself asks for approval
per tool call rather than blanket-approving a whole session up front.

Not building the actual escalation mechanism yet -- there's no
privileged feature to hang it on. This gets built alongside whichever
of `tshark`/`lldpd`/`-O` lands first, not before.

## run.py vs. discover.py, and devices.yml's fate

Decided: `run.py` and `discover.py` stay as two separate entry points,
by design, not a precursor/successor relationship -- they serve
genuinely different workflows. `run.py` is manual/interactive (human
knows the IP, wants one device right now, may not have credentials for
it yet -- `connect_with_pool` prompts and grows the pool). `discover.py`
is automatic/batch (sweep a whole subnet with credentials already on
hand, no keyboard interaction by default).

`devices.yml` (a hand-maintained static device list, originally floated
as a stepping stone before discovery existed) stays on the table as a
possible future feature rather than being closed out -- some sites won't
want a live network scan on every run, and a static list is a legitimate
alternative input for the future Ansible dynamic-inventory bridge, not
just a workaround for discovery not existing yet. Not building it now --
nothing's asking for it yet -- just no longer treating it as "obsoleted
by discover.py existing."

**Auth-failure gap, closed for v1**: `discover.py` used to silently bucket
a host with SSH open but no working pool credential into `unidentified`,
same as a host it had no read on at all. Added an opt-in
`--prompt-on-auth-failure` flag (`discover.py`, `auth.prompt_and_retry_ssh`)
that, only when passed, pauses on exactly that case, asks once whether to
bother entering credentials for this specific host, and on success grows
the pool for the rest of the run -- same shape as `connect_with_pool`,
just opt-in and scoped to hosts nmap already proved have SSH open. Off by
default: a batch scan across a whole subnet shouldn't stop for keyboard
input unless asked to.

## Subnet auto-detection (done)

`discover.py`'s `cidr` argument is now optional. Same idea as `ip route
get`/`route get` on the command line: ask the OS which interface would
be used to reach the outside world (a UDP `connect()` to a public IP,
nothing actually sent, just picks a route), then read that interface's
netmask. New module `subnet_detect.py` uses `psutil` for the netmask
lookup rather than hand-parsing `ifconfig`/`ip addr` text, which differs
enough between macOS and Linux that it's not worth reimplementing --
same call already made for nmap/arp. Confirmed live against this dev
box, picked up its real local subnet correctly on the first try.

If detection fails (no default route, e.g. offline or a weird network
setup), `discover.py` prints a clear message and asks for an explicit
CIDR instead of guessing. Explicit CIDR always overrides auto-detection
when given.

## Single entry point (menu.py)

The collector was five separate scripts with no common front door. Added
`menu.py`: prints a numbered list, says what each tool needs, then hands
off to that tool's own CLI as a subprocess (inherits the terminal, so
`run.py`'s prompts and `discover.py`'s live progress output both still
work exactly as they do run directly). Adding a new tool later is one
more entry in a list, nothing structural changes.

A couple of pieces got a bit smarter specifically to make the menu
useful rather than just a wrapper:

- **Subnet confirm/override**: `menu.py` runs `detect_local_cidr()`
  itself before launching `discover.py`, shows what it found, and asks
  whether to scan that or type a different CIDR instead. `discover.py`
  itself still auto-detects on its own when run directly with no CIDR,
  this is just a confirmation step in front of it.
- **Device list file for run.py**: `run.py` now takes an optional
  `--devices-file`, a plain two-column CSV (`vendor,host`, vendor is
  `juniper` or `exos`). Given a file, it collects that list without
  prompting for each device; without one, the original type-them-in-one-
  at-a-time flow is unchanged. `menu.py` asks which you want.
- **Host/credential override for the one-shot tools**: `collect.py` and
  `collect_unifi.py` only ever read their target from environment
  variables (`NIC_JUNOS_HOST`, `NIC_UNIFI_HOST`, `NIC_UNIFI_API_KEY`).
  Since `menu.py` launches each as a subprocess, it can pass a modified
  `env` for just that one launch, overriding those variables with
  whatever gets typed into the menu. Neither script needed any changes
  for this. Same trick for a one-off credential: `menu.py` can seed
  `NIC_CRED_1_USER`/`NIC_CRED_1_PASS` for that subprocess and the
  existing credential-pool logic in `auth.py` picks it up like it
  always does.

`connect_test.py` stays out of the menu on purpose, it's a throwaway
smoke test, not a real tool.

**Vendor-filtered scan**: there's no standalone single-device EXOS
script (unlike `collect.py` for Juniper), so a menu option added instead:
run the normal `discover.py` subnet scan unchanged, then read back its
own `output/discover_results.json` afterward and print just the records
for one vendor (`extreme` for the EXOS option). The scan itself still
finds everything on the subnet; this only narrows what gets shown after.
Written as a generic `_filter_and_report(vendor)` helper so the same
pattern covers other vendors later without duplicating anything.

**Real nmap concurrency bug found and fixed during live testing**:
`nmap_scan.scan()`'s original implementation had a background thread
reading `stderr` for live progress while the main thread called
`proc.communicate()`, which also tries to read `stderr` itself. Two
readers on the same file descriptor, confirmed live as an `OSError:
[Errno 9] Bad file descriptor`. Existing tests never caught this since
they only test `parse_xml()` directly, never the actual subprocess
plumbing. Fixed by having the main thread read only `stdout` directly
(`proc.stdout.read()`) and calling `proc.wait()` instead of
`communicate()`, so the two threads never touch the same descriptor.
New `test_run_streaming_*` tests in `test_nmap_scan.py` exercise the
real subprocess path (not mocked) to cover this going forward.

**Local device lists**: `run.py --devices-file` reads a path anywhere on
disk, so there's nothing stopping someone from pointing it at a file
inside the repo. Added `lab/*/devices/` to `.gitignore` (same pattern as
`output/`) as a conventional safe spot, and `menu.py` suggests it when
asking for the file path.

## Firmware inventory report

No new device connections at all, pure reporting on data the existing
collectors already gathered. Reads every `*.json` file already sitting
in `output/` (`discover_results.json`, `inventory_run.json`,
`juniper_inventory.json`, `unifi_inventory.json`, whatever's actually
there), normalizes the different shapes each one uses (a dict with a
`records` key, a plain list, or a single dict for the one-device path),
and combines them into one list.

**Dedup needed real thought, not just a host-based key.** The same
device can show up in more than one output file (a one-off `collect.py`
run, then a later `discover.py` sweep), so duplicates get collapsed,
keeping whichever has the newer `collected_at`. But UniFi's `host`
field is the *controller's* address, shared across every device behind
it, not a per-device one (see the UniFi API notes above), so keying the
dedup on `host` alone would have silently collapsed every AP/switch on
one controller into a single record. Keys on `mac_address` first when
present (UniFi always has one), falling back to `host` for the SSH
vendors where it genuinely is per-device.

No known-good version comparison yet, on purpose, that needs an actual
target-version list to compare against, which nothing's defined yet.
This just lists what's out there. Prints to the terminal by default,
only writes `output/firmware_report.csv` if asked, matching the
"terminal output isn't a repo risk, only files are" reasoning already
established for the config-backup-system project.

## Next up

- UniFi per-port/per-radio detail stays the known v1 limitation, on
  purpose. Would need live testing against the real controller to find
  out whether a deeper endpoint even exists, and nothing's asking for
  that detail yet, so parked rather than chased for its own sake.
- Known-good firmware version comparison for the report above, once
  there's an actual target-version list to check against.
