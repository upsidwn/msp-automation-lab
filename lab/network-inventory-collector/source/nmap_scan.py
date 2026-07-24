# Runs nmap and parses its XML output into plain candidate dicts.
# Deliberately a plain TCP connect scan (-sT, not -sS) with no OS
# detection (-O), so this never needs sudo/raw sockets -- keeps it a
# normal user-run tool. Only scans the ports that matter for dispatch
# (SSH for the Junos/EXOS credential pool, HTTP/HTTPS for the UniFi API
# check). MAC address is often unavailable without elevated privileges
# -- callers should treat it as optional, not guaranteed.

import subprocess
import xml.etree.ElementTree as ET

DEFAULT_PORTS = "22,80,443"


def scan(cidr, ports=DEFAULT_PORTS):
    result = subprocess.run(
        ["nmap", "-sT", "-sV", "--open", "-p", ports, "-oX", "-", cidr],
        capture_output=True,
        text=True,
        check=True,
    )
    return parse_xml(result.stdout)


def parse_xml(xml_text):
    root = ET.fromstring(xml_text)
    candidates = []

    for host in root.findall("host"):
        ip = None
        mac = None
        for addr in host.findall("address"):
            if addr.get("addrtype") == "ipv4":
                ip = addr.get("addr")
            elif addr.get("addrtype") == "mac":
                mac = addr.get("addr")

        if not ip:
            continue

        open_ports = []
        ports_el = host.find("ports")
        if ports_el is not None:
            for port in ports_el.findall("port"):
                state = port.find("state")
                if state is None or state.get("state") != "open":
                    continue

                service = port.find("service")
                open_ports.append(
                    {
                        "port": int(port.get("portid")),
                        "protocol": port.get("protocol"),
                        "service": service.get("name") if service is not None else None,
                        "product": service.get("product") if service is not None else None,
                        "version": service.get("version") if service is not None else None,
                    }
                )

        candidates.append({"ip": ip, "mac": mac, "ports": open_ports})

    return candidates
