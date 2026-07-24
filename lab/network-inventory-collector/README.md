# Network Inventory Collector

Status: planning, no code yet. Lives in `lab/` until it's stable enough
to move to `production/`.

## What it does

Connects to network devices and pulls together a standard inventory
report — hostname, vendor, model, serial, firmware, interfaces, IPs.
Basically automating the "log into every device and write down what it
is" step.

## Scope for v1

- Static list of devices (IP/hostname) to start — no auto-discovery yet
- SSH only
- Output: CSV and/or JSON

## Still deciding

- Which vendors/OS first (Cisco IOS? Juniper?)
- Plain Python (Netmiko/Paramiko) vs. an Ansible playbook
- Where the device list comes from (probably a YAML file for now)
- Whether output feeds a NetBox import later or just stands alone

## Notes

Read-only creds only, never hardcoded — see [docs/NOTES.md](../../docs/NOTES.md).

See [docs/ROADMAP.md](../../docs/ROADMAP.md) (Phase 2) for the bigger
picture.
