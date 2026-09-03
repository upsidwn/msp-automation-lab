# Design notes

## Why Ansible, not the collector's Netmiko approach

Netmiko would do config backups fine too. This project exists
specifically to get real hands-on time with Ansible, since it's named
in the repo's own tech stack list but the inventory collector never
actually used it. So the tool choice here is driven by that goal, not
by Netmiko falling short.

## Collection: juniper.device, not junipernetworks.junos

`junipernetworks.junos` looked like the obvious pick going in, it's the
"certified" collection name most Junos Ansible examples reference. But
`ansible-playbook --syntax-check` flagged it live as deprecated the
first time this playbook ran, pointing at `juniper.device` as the
replacement (Juniper's own maintained collection; redirects are
supported until 2028, but no reason to start a new project on a
collection that's already being phased out). Same module name
(`junos_config`), same `backup`/`backup_options` arguments, just a
different collection namespace and its own netconf/cliconf/terminal
plugin set. `ansible_network_os` is `juniper.device.junos` accordingly,
not `junipernetworks.junos.junos`.

## Connection: netconf

Junos speaks netconf natively, and `juniper.device.junos_config`'s
`backup` option is built around it, so `ansible_connection:
ansible.netcommon.netconf` was the natural choice over `network_cli`
(the SSH-and-scrape-CLI-text approach, closer to what Netmiko already
does in the Python collector). Netconf gets structured data instead of
parsing CLI output, which is the whole reason it exists as a protocol.

## Credentials: Ansible Vault, not .env

Deliberately a different pattern from the Python collector's `.env`
approach, since the point is Ansible experience specifically. Real
values live in `group_vars/junos/vault.yml`, encrypted in place with
`ansible-vault encrypt` after being filled in from the `.example`
template. Vault-encrypted content is technically safe to commit (that's
the whole point of Vault), but `vault.yml` itself is still gitignored
here anyway, same as `hosts.yml`, to remove any window where an
accidentally-still-plaintext version could get committed before
encryption happens. No vault password file gets stored on disk either,
`--ask-vault-pass` prompts for it interactively each run instead.

## Inventory: static file for the MVP

A hand-maintained `inventory/hosts.yml` (gitignored, `.example`
committed) is the fastest path to a working playbook, and isolates
"does the playbook itself work" from "does the dynamic inventory bridge
work" as two separate things to debug. Feeding this from
`discover.py`'s scan output instead is a real next step, not abandoned,
just sequenced after the playbook is proven end to end.

## host_key_checking disabled

Set in `ansible.cfg` for lab convenience, this is a private lab network
with borrowed/personal gear, not a hardened environment. Would need
re-enabling (or explicit known_hosts management) before pointing this
at anything closer to production.

## Live run confirmed

First real end-to-end test, against the actual lab switch (booted for
the occasion). `ansible-playbook backup.yml --ask-vault-pass` connected
over netconf, decrypted the vault, and wrote a real timestamped backup
(`lab-switch-1_config.<timestamp>`, 97 lines of `set`-style config) to
`output/`. That filename has no fixed extension, unlike the collector's
own `*.json`/`*.csv` output, so `.gitignore` needed a plain `output/*`
pattern here instead of an extension-based one.

Same discovery-probe timing issue noted in the collector's own design
notes (a slow-to-respond device needing `-Pn`/`--thorough` rather than
the fast default) came up again here independently, this switch is
just slow to answer network probes in general, not specific to nmap.

## EXOS: no maintained collection exists

Went looking for an EXOS-equivalent to `juniper.device` and came up
short. `extremenetworks.exos` isn't a real package on Galaxy.
`community.network` has `exos_config`/`exos_command` modules, but the
whole collection is marked deprecated in its own module docs
(`alternative: Unknown`), not a "use the newer one" situation like
`junipernetworks.junos` -> `juniper.device` was.

The connection plugins are the part that actually matters here, though:
EXOS talks `network_cli` (SSH + CLI scraping), not netconf, and
`community.network` is the only source for the EXOS-specific
cliconf/terminal plugins that teach Ansible how to handle its prompts.
Nothing else provides those. So the plan is: keep using
`community.network`'s connection plugins (`ansible_network_os:
community.network.exos`), but skip its deprecated `exos_config` module
and use the actively-maintained generic `ansible.netcommon.cli_command`
instead, running `show config` (confirmed live via manual SSH, this
switch's actual command for a full config dump) and writing the output
to a timestamped file by hand with `ansible.builtin.copy`, matching the
same `<hostname>_config.<date>@<time>` naming `junos_config`'s backup
option uses automatically. `ansible.builtin.strftime` (a core Ansible
filter, not a dependency) builds the timestamp on the control node
since these plays run with `gather_facts: no`.

Real limitation, not swept under the rug: this whole path leans on a
collection with no maintained future. If `community.network`'s EXOS
plugins ever stop working on a newer ansible-core, the honest fallback
is hand-writing a terminal/cliconf plugin, or dropping to `network_cli`
with `ansible.netcommon.cli_command`'s own more primitive prompt
handling. Not needed yet, just the known ceiling here.

## Live run confirmed (EXOS)

`ansible-playbook backup.yml --ask-vault-pass --limit exos` connected
over SSH via `community.network`'s cliconf/terminal plugins, ran `show
config`, and wrote a real 283-line backup
(`lab-switch-2_config.<timestamp>`) to `output/`, same `output/*`
gitignore pattern as the Junos side covers this too.

## Dynamic inventory bridge

`source/dynamic_inventory.py` implements Ansible's inventory script
contract directly (an executable that prints the right JSON when called
with `--list`), rather than a formal Ansible inventory plugin. Much
less ceremony for the same result, and the script contract is simple
enough that a plugin class would just be more code for no real benefit
here.

**Group names, not vendor names.** `discover.py`'s records use
`"vendor": "juniper"` / `"extreme"`, but the existing static inventory's
groups are named `junos`/`exos` (matching the collections/connection
setup, not the vendor string). The bridge maps `juniper -> junos`,
`extreme -> exos` explicitly rather than assuming they'd ever match.
UniFi records get skipped outright, there's no UniFi playbook in this
project to feed.

**Credentials needed zero changes.** Ansible resolves `group_vars` by
group membership, not by which inventory source produced that
membership. So a host arriving via the dynamic bridge into the `junos`
group picks up `group_vars/junos/vars.yml` and `vault.yml` exactly the
same as one from the static `hosts.yml`. This is exactly why the IP/
device-list-carryover idea from the credential discussion was safe to
build: it never touches how creds get resolved at all.

**Host naming**: uses `hostname` when a device reports one, falls back
to its IP when it doesn't (the Junos lab switch is vanilla/unconfigured
and reports `hostname: null`, same gap noted in the collector's own
design notes). Guards against a host appearing twice in one group's
list even if the same device shows up twice in `records` (didn't happen
in testing, cheap to guard against anyway).

**Confirmed working**: both as a standalone script against the real
`discover_results.json`, and through Ansible's own `ansible-inventory
--list` validation, correctly grouping the real Junos and EXOS lab
switches with the right `ansible_host` values.

Static `hosts.yml` stays as-is and stays the default (`ansible.cfg`
still points at it), this is an alternative source you opt into with
`-i dynamic_inventory.py`, not a replacement.

## EXOS config push: cli_config, not hand-rolled idempotency

Junos access isn't available right now, so the next feature is
EXOS-only: `configure_vlan.yml`, a playbook that actually changes
device state (create a VLAN, tag it to a port) instead of just reading
it, the way `backup.yml` does.

No `junos_vlans`-style resource module exists for EXOS (same gap noted
above), so there's no framework computing "desired state vs actual
state" automatically. The alternative isn't "give up on idempotency
and just re-run commands every time" though - `ansible.netcommon.
cli_config` is a generic, vendor-agnostic module built for exactly
this: it takes a block of config text, evaluates the device's current
config, and only pushes what's not already present. Real check-mode/
`--diff` support too, so "show me what would change" works before
anything touches the switch.

First draft got the module's own interface wrong: assumed a `lines`
list (that's `ios_config`/other resource-module conventions), actual
parameter is `config`, a single text block. `ansible-lint` caught it
immediately (`Unsupported parameters... Supported parameters include:
... config ...`), fixed before it ever got near a real device. Also
switched "persist the change" from a plain `when: config_result.
changed` task to a proper handler (`notify`/`meta: flush_handlers`) -
ansible-lint's `no-handler` rule flagged the original as the wrong
idiom for "only do this if something upstream changed," and the
handler version is what gets `backup.yml`'s own "production" profile
result, so this playbook matches that bar too.

**Open question, not yet resolved**: `cli_config` depends on the
network_os's cliconf plugin implementing `edit_config()` under the
hood. `community.network`'s EXOS cliconf plugin is what `backup.yml`
already relies on for the connection itself, but whether it actually
supports the diffing/edit_config behavior `cli_config` needs hasn't
been confirmed, `community.network` is deprecated with no docs
promising it. Real limitation, not swept under the rug: if it turns
out not to work, the honest fallback is hand-rolled idempotency
instead - pull `show vlan` first, parse whether the VLAN/port already
matches, only issue the create/configure commands via the same
`cli_command` module `backup.yml` already uses if it doesn't.

## Live run confirmed (configure_vlan.yml, --check --diff)

Both open questions above are resolved. Against the real EXOS lab
switch (`lab-switch-2`), `--check --diff` showed `cli_config` correctly
computed all three lines as missing and would push them:

```
create vlan test100
configure vlan test100 tag 100
configure vlan test100 add ports 1:20 tagged
```

So `community.network`'s EXOS cliconf plugin does support the
diffing/edit_config behavior `cli_config` needs, and the hand-written
command syntax was right the first time.

**Real bug found and fixed**: the handler (`save configuration`) and
the post-change verification tasks weren't guarded for check mode.
`ansible.netcommon.cli_command` refuses to actually run anything that
isn't a `show` command while `--check` is set (confirmed live -
"Only show commands are supported when using check_mode, not executing
save configuration"), and separately, since check mode never really
pushes the config, verifying the port landed in the VLAN would have
failed for the wrong reason (nothing changed, not "something's
broken"). Fixed with `when: not ansible_check_mode` on the handler,
the post-change snapshot, and the assert - a `--check --diff` run now
shows the proposed diff and stops cleanly, no false failures.

Cosmetic-only, not investigated further: `cli_config`'s own
idempotency-guidance warning printed as one `[WARNING]` line per
character during this run instead of one readable line. Didn't affect
the actual result (the diff and the correct commands both came
through fine), looked like an output-formatting quirk in this
`ansible-core` version rather than anything wrong with the playbook.

## Live run confirmed (configure_vlan.yml, real run - found the actual limitation)

First real (non-check-mode) run against `lab-switch-2`, with
`vlan_port=1:20`. Two real, non-cosmetic problems surfaced, both fixed:

**1. `1:20` was the wrong port-ID format for this switch.**
`configure vlan test100 add ports 1:20 tagged` failed device-side:
`Invalid slot-port-channel separator detected`. `create vlan test100`
and `configure vlan test100 tag 100` had already succeeded by that
point in the same task, so the VLAN existed on the device, tagged,
with zero ports, and unsaved (the failed task meant the notify never
fired, so `save configuration` never ran either - confirmed nothing
persisted). The right way to get a device's actual port-ID convention
turned out to be `show ports information` run directly over SSH,
rather than guessing at EXOS conventions from memory a second time.

**2. The bigger finding: `create vlan` isn't idempotent through
`cli_config`, confirmed by the immediate next run failing differently**:
```
create vlan test100
%% Name test100 is already in use.
```
`cli_config` re-sent `create vlan test100` even though it already
existed, because - as the design section above predicted as an open
risk - `create vlan` is a one-shot action, not a declarative line
reflected verbatim in the running config the way `configure vlan ...
tag ...` is. `cli_config`'s diff engine had nothing to match it
against, so it never treated it as already-satisfied. This is the
"honest fallback" scenario, now confirmed real rather than
hypothetical: `create vlan` is hand-rolled idempotent now (a
`set_fact` checking `vlan_name in pre_change_vlans.stdout`, gating a
separate `cli_command` task), while `configure vlan ... tag ...` and
`configure vlan ... add ports ... tagged` stay on `cli_config`, which
handled those correctly both times (no false rejections, no duplicate
pushes).

Also worth noting: the failed `cli_config` task in run 1 reported
`"changed": false` in its own fatal error output, despite two of its
three lines having actually applied to the device. `cli_config` here
doesn't distinguish "nothing happened" from "partially applied, then
hit an error" in what it reports - real limitation, not something this
playbook works around, just something to know if a future failure ever
looks like a clean no-op when it wasn't.

Cosmetic-only, not investigated further: `cli_config`'s own
idempotency-guidance warning printed as one `[WARNING]` line per
character during the earlier `--check --diff` run instead of one
readable line. Didn't affect either real run's actual result.

## Port-ID format confirmed: plain numbers, no slot prefix

`show ports information` on the real switch lists ports as bare
numbers (`1`, `2`, ... `56`), not `slot:port`. Confirmed a second way
too: the switch's own error on `sh vlan ports 1:20` was explicit -
"Invalid slot-port-channel separator detected... A number within the
range of 1-4094 is expected." `1:20` isn't invalid EXOS syntax in
general, it's the standard form on stacked/modular hardware - this
particular switch is a standalone unit, so it wants just `20`. Nothing
in the playbook needed to change for this, `vlan_port` is a runtime
extra-var either way, just a different value going forward
(`-e vlan_port=20`, not `-e vlan_port=1:20`). Worth remembering if this
ever points at different EXOS hardware: the port-ID convention isn't
fixed across the vendor, it's per-switch, and `show ports information`
is the reliable way to check rather than assuming.

## Live run confirmed (configure_vlan.yml, both real and idempotent no-op)

Two consecutive real runs with the corrected `vlan_port=20`, everything
this playbook was actually built to prove came through:

**Run 1** (real change): `Create the VLAN` task skipped -
`vlan_already_exists` correctly matched `test100` from the pre-change
snapshot (leftover from the earlier broken attempts). `cli_config`
pushed only `configure vlan test100 add ports 20 tagged` - it
correctly recognized `configure vlan test100 tag 100` was *already*
present in the running config (applied days earlier, before the
port-syntax failure) and didn't resend it. That's real evidence
`cli_config`'s diffing is genuinely comparing against device state,
not just "did I run this exact block before."

**Run 2** (idempotent no-op, same command unchanged): `Create the VLAN`
skipped again, and this time `cli_config` itself reported `ok`, not
`changed` - nothing left to push. No `RUNNING HANDLER` line at all,
confirming `notify` correctly never fired. Post-change verification
ran, showed the real device state (`Tag: 20` under the VLAN's port
list), and the assert passed: `"Confirmed: port 20 is tagged into VLAN
test100"`.

**Real bug found**: `save configuration` timed out in run 1 -
`network_cli`'s default 30s command timeout is too short for this
switch's flash write. Since nothing changed in run 2, the handler
never got a second chance to retry it either - the verified-correct
config sat unsaved (visible as the `*` prefix EXOS's own prompt shows
for pending changes) until saved manually. Fixed by setting
`ansible_command_timeout: 60` in `group_vars/exos/vars.yml` - not yet
re-confirmed live, the next real change through this playbook (not a
no-op) will be the first real test of whether 60s is actually enough.

## Next up

Nothing blocking. The core idempotency behavior (real push, precise
diffing, clean no-op, hand-rolled create-vlan fallback) is fully
live-confirmed. The only open thread is confirming the
`ansible_command_timeout` fix on a future real change, whenever one
happens to come up naturally - not worth manufacturing a throwaway
change just to test a timeout value.
