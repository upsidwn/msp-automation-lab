# Parses Junos `| display json` output into plain inventory dicts.
# Junos wraps every leaf value as [{"data": ...}], so _first_data()
# exists to stop repeating that unwrap everywhere.

import json
from datetime import datetime, timezone

COMMANDS = {
    "version": "show version | display json",
    "hardware": "show chassis hardware | display json",
    "interfaces": "show interfaces terse | display json",
}


def _first_data(items):
    if not items:
        return None
    first = items[0]
    return first.get("data") if isinstance(first, dict) else None


def parse_version(raw_json):
    data = json.loads(raw_json)
    re_item = data["multi-routing-engine-results"][0]["multi-routing-engine-item"][0]
    software = re_item["software-information"][0]

    return {
        "hostname": _first_data(software.get("host-name")),
        "vendor": "juniper",
        "model": _first_data(software.get("product-model")),
        "firmware": _first_data(software.get("junos-version")),
    }


def parse_hardware(raw_json):
    data = json.loads(raw_json)
    chassis = data["chassis-inventory"][0]["chassis"][0]

    return {"serial": _first_data(chassis.get("serial-number"))}


def parse_interfaces(raw_json):
    data = json.loads(raw_json)
    physical = data["interface-information"][0].get("physical-interface", [])

    interfaces = []
    for iface in physical:
        ips = []
        for logical in iface.get("logical-interface", []):
            for af in logical.get("address-family", []):
                for addr in af.get("interface-address", []):
                    ip = _first_data(addr.get("ifa-local"))
                    if ip:
                        ips.append(ip)

        interfaces.append(
            {
                "name": _first_data(iface.get("name")),
                "admin_status": _first_data(iface.get("admin-status")),
                "oper_status": _first_data(iface.get("oper-status")),
                "ip_addresses": ips,
            }
        )

    return interfaces


def collect(conn, host):
    """Runs the inventory commands over an already-connected Netmiko
    session and returns one merged record. Shared by the single-device
    CLI (collect.py) and the multi-device interactive runner (run.py).
    """
    raw = {key: conn.send_command(cmd, read_timeout=30) for key, cmd in COMMANDS.items()}

    record = parse_version(raw["version"])
    record["host"] = host
    record["serial"] = parse_hardware(raw["hardware"])["serial"]
    record["interfaces"] = parse_interfaces(raw["interfaces"])
    record["collected_at"] = datetime.now(timezone.utc).isoformat()

    return record
