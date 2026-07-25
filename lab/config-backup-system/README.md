# Configuration Backup System

Status: working against both the Juniper and EXOS lab switches. An
Ansible playbook that backs up Junos and EXOS devices' running configs
to timestamped local files. First real use of Ansible in this repo, the
inventory collector uses Python/Netmiko directly instead (see
[lab/network-inventory-collector](../network-inventory-collector)).

## What it does

Connects to each device (netconf for Junos, SSH/CLI for EXOS) and saves
its running config to `output/`, one timestamped file per run.
Read-only against the device, no config changes ever get pushed.

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
- `source/backup.yml`: the playbook, one play per vendor
- `output/`: where backups land, gitignored (real device configs)
- `tests/test_playbook.py`: validates the example files' YAML shape, runs `ansible-playbook --syntax-check`

## Status

- [x] Playbook scaffolded, syntax-checked, structure covered by tests
- [x] Run live against the real Junos lab switch, confirmed working
- [x] Run live against the real EXOS lab switch, confirmed working
- [ ] Feed inventory from `discover.py`'s output instead of a static file

## Notes

Read-only creds only, never hardcoded (see [docs/NOTES.md](../../docs/NOTES.md)).

See [docs/ROADMAP.md](../../docs/ROADMAP.md) (Phase 2) for the bigger picture.
