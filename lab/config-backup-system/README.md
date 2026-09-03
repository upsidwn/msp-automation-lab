# Configuration Backup System

Status: working against both the Juniper and EXOS lab switches. An
Ansible playbook that backs up Junos and EXOS devices' running configs
to timestamped local files. First real use of Ansible in this repo, the
inventory collector uses Python/Netmiko directly instead (see
[lab/network-inventory-collector](../network-inventory-collector)).

Also now has a second, EXOS-only playbook that actually pushes config
changes (`configure_vlan.yml`), and a third pair that does drift
detection (`set_baseline.yml` / `check_drift.yml`). See below.

## What it does

`backup.yml` connects to each device (netconf for Junos, SSH/CLI for
EXOS) and saves its running config to `output/`, one timestamped file
per run. Read-only against the device, no config changes ever get
pushed.

`configure_vlan.yml` (EXOS only) is the opposite: it creates a VLAN and
tags it to a port. Idempotent (no EXOS resource-module collection
exists to do this the `junos_vlans`-style way): `configure vlan ...
tag ...` and `... add ports ... tagged` go through `ansible.netcommon.
cli_config`, which diffs against the running config, while `create
vlan` is hand-rolled idempotent since it's a one-shot action `cli_config`
can't diff (confirmed live, see
[documentation/design-notes.md](documentation/design-notes.md) for
why). Takes before/after `show vlan` snapshots to `output/`, and fails
loud if the port doesn't actually land in the VLAN. `vlan_port`'s
format isn't fixed across EXOS hardware, check `show ports information`
on the real device rather than assuming (a standalone switch takes a
plain port number, stacked/modular hardware may need `slot:port`).
Run with `--check --diff` first:

```
ansible-playbook configure_vlan.yml --limit exos --ask-vault-pass \
  -e vlan_name=test100 -e vlan_id=100 -e vlan_port=20 --check --diff
```

`set_baseline.yml` / `check_drift.yml` (EXOS only) are config
compliance, drift-detection style: `set_baseline.yml` pulls the
current running config and saves it as the "known good" reference for
that device (`known_good/<hostname>_config.golden`, gitignored - a
real full config, same risk class as `output/`). `check_drift.yml`
pulls the current config again later and diffs it against that
baseline with real `diff -u`, reporting either "no drift" or the
actual diff to `output/`. Not a rules-based compliance checker
(deliberately not - see
[documentation/design-notes.md](documentation/design-notes.md) for
why), this is "does the device still match what it matched before."
`set_baseline.yml` refuses to run without an explicit confirmation
flag, re-baselining over undetected drift would make that drift
invisible:

```
ansible-playbook set_baseline.yml --limit exos --ask-vault-pass \
  -e confirm_baseline_update=true
ansible-playbook check_drift.yml --limit exos --ask-vault-pass
```

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r source/requirements.txt
cd source
ansible-galaxy collection install -r requirements.yml

cp inventory/hosts.yml.example inventory/hosts.yml
# edit inventory/hosts.yml, fill in the real device IPs

cp group_vars/junos/vault.yml.example group_vars/junos/vault.yml
# edit group_vars/junos/vault.yml, fill in the real username/password
ansible-vault encrypt group_vars/junos/vault.yml

cp group_vars/exos/vault.yml.example group_vars/exos/vault.yml
# edit group_vars/exos/vault.yml, fill in the real username/password
ansible-vault encrypt group_vars/exos/vault.yml

ansible-playbook backup.yml --ask-vault-pass
```

`hosts.yml` and both `vault.yml` files are gitignored, only the
`.example` placeholders get committed. Running the whole playbook
backs up every device in inventory; add `--limit junos` or `--limit
exos` to target just one vendor.

## Dynamic inventory, alternative to the static hosts.yml

`source/dynamic_inventory.py` reads
[lab/network-inventory-collector](../network-inventory-collector)'s own
`discover.py` output and exposes it as Ansible inventory instead of
hand-maintaining `hosts.yml`. Use it by pointing Ansible at it directly:

```
ansible-playbook backup.yml -i dynamic_inventory.py --ask-vault-pass
```

Groups devices by vendor (`juniper` -> `junos`, `extreme` -> `exos`),
same group names the static inventory uses, so credentials still come
from `group_vars/<group>/vars.yml` + `vault.yml` exactly the same way.
UniFi records are skipped, no UniFi playbook exists here. Static
`hosts.yml` still works and stays the default, this is an alternative
source, not a replacement, point Ansible at whichever one you want with
`-i`.

## Why Ansible here, not Netmiko like the collector

Netmiko would work fine for this too. The point of this project is
hands-on Ansible experience specifically, not that Netmiko couldn't do
config backups. See [documentation/design-notes.md](documentation/design-notes.md)
for the actual tool choices made and why.

## Source layout

- `source/ansible.cfg`: project-local config, points at `inventory/hosts.yml`
- `source/requirements.txt`: pip deps (`ansible-core`, PyEZ, `ncclient`)
- `source/requirements.yml`: Galaxy collections (`juniper.device`, `ansible.netcommon`, `community.network`)
- `source/inventory/hosts.yml.example`: placeholder inventory, one Junos host, one EXOS host
- `source/group_vars/junos/vars.yml`: connection vars for the junos group (netconf, network_os)
- `source/group_vars/junos/vault.yml.example`: placeholder credential vars, encrypt after filling in
- `source/group_vars/exos/vars.yml`: connection vars for the exos group (network_cli, network_os)
- `source/group_vars/exos/vault.yml.example`: placeholder credential vars, encrypt after filling in
- `source/backup.yml`: the read-only backup playbook, one play per vendor
- `source/configure_vlan.yml`: EXOS-only, pushes a real VLAN/port config change, idempotent via `cli_config`
- `source/set_baseline.yml`: EXOS-only, saves the current running config as the drift-detection baseline
- `source/check_drift.yml`: EXOS-only, diffs the current running config against that baseline
- `source/dynamic_inventory.py`: alternative inventory source, reads `discover.py`'s output instead of a static file
- `output/`: where backups, configure_vlan's before/after snapshots, and drift reports land, gitignored (real device configs)
- `known_good/`: drift-detection baselines, gitignored (a real full device config, same risk class as `output/`)
- `tests/test_playbook.py`: validates the example files' YAML shape, runs `ansible-playbook --syntax-check`
- `tests/test_configure_vlan.py`: same, for `configure_vlan.yml`
- `tests/test_drift_detection.py`: same, for `set_baseline.yml` and `check_drift.yml`
- `tests/test_dynamic_inventory.py`: validates the bridge script's output, including a real subprocess run

## Status

- [x] Playbook scaffolded, syntax-checked, structure covered by tests
- [x] Run live against the real Junos lab switch, confirmed working
- [x] Run live against the real EXOS lab switch, confirmed working
- [x] Dynamic inventory from `discover.py`'s output, confirmed working via `ansible-inventory`
- [x] `configure_vlan.yml`: run live against the real EXOS switch, both a real change and a real idempotent no-op confirmed working (see design-notes.md for the two real bugs found and fixed along the way - hand-rolled `create vlan` idempotency, and a `save configuration` timeout)
- [x] `set_baseline.yml` / `check_drift.yml`: run live against the real EXOS switch, no-drift case confirmed twice (see design-notes.md - the actual detected-drift branch is still unexercised, though it's standard `diff -u` behavior, not new EXOS-specific guesswork)

## Notes

Read-only creds only, never hardcoded (see [docs/NOTES.md](../../docs/NOTES.md)).

See [docs/ROADMAP.md](../../docs/ROADMAP.md) (Phase 2) for the bigger picture.
