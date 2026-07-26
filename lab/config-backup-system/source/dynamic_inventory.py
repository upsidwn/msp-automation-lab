#!/usr/bin/env python3
# Dynamic Ansible inventory bridge: reads the network inventory
# collector's own discover.py output and exposes it as Ansible's --list
# JSON contract, grouped by vendor (junos/exos), instead of hand
# maintaining hosts.yml. Static hosts.yml stays available too, this is
# an alternative source, not a replacement, point Ansible at this
# script explicitly to use it: `ansible-playbook backup.yml -i
# dynamic_inventory.py`.
#
# UniFi records are skipped, no UniFi playbook exists in this project.
# Credentials still come from group_vars/<group>/vars.yml + vault.yml
# exactly like the static inventory, group_vars loading is based on
# group membership, it doesn't care whether the inventory itself is
# static or dynamic.

import argparse
import json
import os
import sys

DEFAULT_DISCOVER_OUTPUT = os.path.join(
    os.path.dirname(__file__), "..", "..", "network-inventory-collector", "output", "discover_results.json"
)

VENDOR_TO_GROUP = {
    "juniper": "junos",
    "extreme": "exos",
}


def _discover_output_path():
    return os.environ.get("NIC_DISCOVER_OUTPUT", DEFAULT_DISCOVER_OUTPUT)


def load_records(path=None):
    path = path or _discover_output_path()
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as e:
        print(f"Warning: could not parse {path}: {e}", file=sys.stderr)
        return []

    return data.get("records", [])


def build_inventory(records):
    groups = {group: {"hosts": []} for group in VENDOR_TO_GROUP.values()}
    hostvars = {}

    for record in records:
        group = VENDOR_TO_GROUP.get(record.get("vendor"))
        if group is None:
            continue

        name = record.get("hostname") or record.get("host")
        if not name:
            continue

        if name not in hostvars:
            groups[group]["hosts"].append(name)
        hostvars[name] = {"ansible_host": record.get("host")}

    inventory = {"_meta": {"hostvars": hostvars}}
    inventory.update(groups)
    return inventory


def main():
    parser = argparse.ArgumentParser(description="Ansible dynamic inventory bridge from discover.py output.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="Print the full inventory (Ansible's default call).")
    group.add_argument(
        "--host",
        help="Print one host's vars. Always empty here, --list already includes _meta.hostvars.",
    )
    args = parser.parse_args()

    if args.host:
        print(json.dumps({}))
        return

    print(json.dumps(build_inventory(load_records()), indent=2))


if __name__ == "__main__":
    main()
