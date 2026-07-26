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

## Next up

Nothing queued for this project right now. Both vendors work end to
end, live-confirmed, with both a static and dynamic inventory path.
