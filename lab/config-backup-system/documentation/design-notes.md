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
`output/`, confirmed gitignored despite the filename having no fixed
extension (the earlier gitignore patterns were all `*.json`/`*.csv`
style, this one needed a plain `output/*` pattern instead).

Same discovery-probe timing issue noted in the collector's own design
notes (a slow-to-respond device needing `-Pn`/`--thorough` rather than
the fast default) came up again here independently, this switch is
just slow to answer network probes in general, not specific to nmap.

## Next up

- EXOS support, no Extreme-specific Ansible collection has been
  investigated yet, may end up needing `ansible.netcommon`'s generic
  `cli_command`/`cli_config` instead of a vendor collection.
- Dynamic inventory bridge from `discover.py`'s output, once the static
  version above is proven working.
