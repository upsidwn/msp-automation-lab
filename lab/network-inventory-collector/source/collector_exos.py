# Parses Extreme EXOS CLI text output into the same record shape as
# collector.py (Junos). EXOS has no JSON pipe like Junos's `| display
# json`, so this is plain-text regex parsing against `show version`,
# `show switch`, `show ports info detail`, and `show vlan`.

import re
from datetime import datetime, timezone

COMMANDS = {
    "version": "show version",
    "switch": "show switch",
    "ports": "show ports info detail",
    "vlan": "show vlan",
}


def parse_version(raw_text):
    firmware_match = re.search(r"IMG:\s*(\S+)", raw_text)
    serial_match = re.search(r"^Switch\s*:\s*\S+\s+(\S+)\s+Rev", raw_text, re.MULTILINE)

    return {
        "firmware": firmware_match.group(1) if firmware_match else None,
        "serial": serial_match.group(1) if serial_match else None,
    }


def parse_switch(raw_text):
    def field(label):
        match = re.search(rf"^{label}:\s*(.+)$", raw_text, re.MULTILINE)
        return match.group(1).strip() or None if match else None

    return {
        "hostname": field("SysName"),
        "vendor": "extreme",
        "model": field("System Type"),
    }


def parse_ports(raw_text):
    """`show ports info detail` gives one block per port, e.g.:

        Port:	32
        	Admin state:	Enabled with  auto-speed sensing  auto-duplex
        	Link State:	Ready

    Admin state and Link State are genuinely independent here (unlike the
    old `show ports information` table, which only exposed one combined
    link-state column) -- so admin_status and oper_status are no longer
    forced to mirror each other.
    """
    interfaces = []
    blocks = re.split(r"\nPort:\s*", raw_text)[1:]

    for block in blocks:
        port_match = re.match(r"(\S+)", block)
        if not port_match:
            continue

        admin_match = re.search(r"Admin state:\s*(\w+)", block)
        link_match = re.search(r"Link State:\s*(\w+)", block)

        admin_state = admin_match.group(1) if admin_match else None
        link_state = link_match.group(1) if link_match else None

        interfaces.append(
            {
                "name": port_match.group(1),
                "admin_status": "up" if admin_state == "Enabled" else "down",
                "oper_status": "up" if link_state == "Active" else "down",
                "ip_addresses": [],
            }
        )

    return interfaces


def parse_vlan_interfaces(raw_text):
    """EXOS assigns IPs to VLANs, not physical ports -- these show up as
    their own entries alongside the port list, similar to how Junos's
    `irb` interface carries the switch's own IP.
    """
    interfaces = []
    for line in raw_text.splitlines():
        match = re.match(r"^(\S+)\s+(\d+)\s+(\d{1,3}(?:\.\d{1,3}){3})\s*/(\d+)", line)
        if not match:
            continue

        name, _vid, ip, prefix = match.groups()
        interfaces.append(
            {
                "name": f"vlan-{name}",
                "admin_status": "up",
                "oper_status": "up",
                "ip_addresses": [f"{ip}/{prefix}"],
            }
        )

    return interfaces


def collect(conn, host):
    raw_version = conn.send_command(COMMANDS["version"])
    raw_switch = conn.send_command(COMMANDS["switch"])
    raw_ports = conn.send_command(COMMANDS["ports"], read_timeout=60)
    raw_vlan = conn.send_command(COMMANDS["vlan"])

    record = parse_switch(raw_switch)
    record["host"] = host
    record.update(parse_version(raw_version))
    record["interfaces"] = parse_ports(raw_ports) + parse_vlan_interfaces(raw_vlan)
    record["collected_at"] = datetime.now(timezone.utc).isoformat()

    return record
