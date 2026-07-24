# Parses Junos `| display json` output into plain inventory dicts.
# Junos wraps every leaf value as [{"data": ...}], so _first_data()
# exists to stop repeating that unwrap everywhere.

import json


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
