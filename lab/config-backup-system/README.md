# Configuration Backup System

Status: working against the Juniper lab switch. An Ansible playbook
that backs up a Junos device's running config to a timestamped local
file. First real use of Ansible in this repo, the inventory collector
uses Python/Netmiko directly instead (see
[lab/network-inventory-collector](../network-inventory-collector)).

## What it does

Connects to a Junos device over netconf and saves its running config to
`output/`, one timestamped file per run. Read-only against the device,
no config changes ever get pushed.

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r source/requirements.txt
cd source
ansible-galaxy collection install -r requirements.yml

cp inventory/hosts.yml.example inventory/hosts.yml
# edit inventory/hosts.yml, fill in the real device IP

cp group_vars/junos/vault.yml.example group_vars/junos/vault.yml
# edit group_vars/junos/vault.yml, fill in the real username/password
ansible-vault encrypt group_vars/junos/vault.yml

ansible-playbook backup.yml --ask-vault-pass
```

`hosts.yml` and `vault.yml` are both gitignored, only the `.example`
placeholders get committed.

## Why Ansible here, not Netmiko like the collector

Netmiko would work fine for this too. The point of this project is
hands-on Ansible experience specifically, not that Netmiko couldn't do
config backups. See [documentation/design-notes.md](documentation/design-notes.md)
for the actual tool choices made and why.

## Source layout

- `source/ansible.cfg`: project-local config, points at `inventory/hosts.yml`
- `source/requirements.txt`: pip deps (`ansible-core`, PyEZ, `ncclient`)
- `source/requirements.yml`: Galaxy collections (`juniper.device`, `ansible.netcommon`)
- `source/inventory/hosts.yml.example`: placeholder single-host inventory
- `source/group_vars/junos/vars.yml`: connection vars for the junos group (netconf, network_os)
- `source/group_vars/junos/vault.yml.example`: placeholder credential vars, encrypt after filling in
- `source/backup.yml`: the playbook
- `output/`: where backups land, gitignored (real device configs)
- `tests/test_playbook.py`: validates the example files' YAML shape, runs `ansible-playbook --syntax-check`

## Status

- [x] Playbook scaffolded, syntax-checked, structure covered by tests
- [x] Run live against the real lab switch, confirmed working
- [ ] EXOS support
- [ ] Feed inventory from `discover.py`'s output instead of a static file

## Notes

Read-only creds only, never hardcoded (see [docs/NOTES.md](../../docs/NOTES.md)).

See [docs/ROADMAP.md](../../docs/ROADMAP.md) (Phase 2) for the bigger picture.
