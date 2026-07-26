# Draws a device diagram from whatever's already collected in output/,
# grouped by vendor. Reuses firmware_report.load_all_records(), no new
# device connections. This is an inventory diagram, not a topology map:
# no LLDP/link data exists yet to show which port connects to what, see
# design-notes.md. The hub node is the real default gateway when it can
# be identified among the collected records, a generic "Network" label
# otherwise.

import os
import subprocess
import sys

import graphviz
from firmware_report import load_all_records

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

VENDOR_COLORS = {
    "juniper": "lightblue",
    "extreme": "lightgreen",
    "unifi": "lightyellow",
}
DEFAULT_COLOR = "lightgrey"


def default_gateway_ip():
    try:
        if sys.platform == "darwin":
            result = subprocess.run(["route", "-n", "get", "default"], capture_output=True, text=True, check=False)
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("gateway:"):
                    return line.split(":", 1)[1].strip()
        else:
            result = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, check=False)
            parts = result.stdout.split()
            if "via" in parts:
                return parts[parts.index("via") + 1]
    except (FileNotFoundError, OSError):
        pass

    return None


GATEWAY_MODEL_HINTS = ("UDM", "USG", "Dream Machine", "Security Gateway")


def _interface_ips(record):
    return {ip.split("/")[0] for iface in (record.get("interfaces") or []) for ip in (iface.get("ip_addresses") or [])}


def _matches_gateway_ip(record, gateway_ip):
    # UniFi's top-level "host" is the controller's address, shared by
    # every device behind it, not per-device (same quirk noted in
    # firmware_report.py's dedupe logic). That means host alone can
    # over-match, so also check each device's own interface IP.
    return record.get("host") == gateway_ip or gateway_ip in _interface_ips(record)


def _looks_like_gateway_model(record):
    model = record.get("model") or ""
    return any(hint in model for hint in GATEWAY_MODEL_HINTS)


def _find_gateway_record(records, gateway_ip):
    if not gateway_ip:
        return None

    candidates = [r for r in records if _matches_gateway_ip(r, gateway_ip)]

    # UniFi's "host" is the shared controller address handed back for
    # every adopted device (see _matches_gateway_ip above), so a UniFi
    # record matching on host alone is never proof by itself of being the
    # actual gateway/console, even when it's the only UniFi candidate that
    # happens to be present. Only trust a lone match outright when it's a
    # non-UniFi vendor, whose "host" is a genuine per-device address.
    if len(candidates) == 1 and candidates[0].get("vendor") != "unifi":
        return candidates[0]

    # Either zero candidates, more than one, or a single UniFi candidate
    # that still needs model verification: we're likely looking at (part
    # of) a UniFi controller's device list, where every device shares the
    # same host value. The console device itself (UDM/USG/etc) is the only
    # one that should count as the gateway. Its own interface IP is its
    # WAN address, not the LAN gateway IP, so it only shows up here via
    # the shared host match, same as the other devices. If nothing looks
    # gateway-shaped, don't guess, let it fall back to the generic label.
    gateway_shaped = [r for r in candidates if _looks_like_gateway_model(r)]
    if len(gateway_shaped) == 1:
        return gateway_shaped[0]

    return None


def build_diagram(records, gateway_ip=None):
    dot = graphviz.Graph("network", format="png")
    dot.attr(rankdir="TB")

    gateway_record = _find_gateway_record(records, gateway_ip)
    if gateway_record:
        name = gateway_record.get("hostname") or gateway_record.get("host")
        model = gateway_record.get("model") or ""
        hub_label = f"{name}\n{model} (gateway)"
    else:
        hub_label = "Network"

    dot.node("network", hub_label, shape="doubleoctagon")

    for i, record in enumerate(records):
        if record is gateway_record:
            continue

        node_id = f"device{i}"
        name = record.get("hostname") or record.get("host") or "(unknown)"
        model = record.get("model") or "(unknown model)"
        color = VENDOR_COLORS.get(record.get("vendor"), DEFAULT_COLOR)

        dot.node(node_id, f"{name}\n{model}", style="filled", fillcolor=color)
        dot.edge("network", node_id)

    return dot


def main():
    records = load_all_records()
    if not records:
        print("No collected inventory found in output/, run a collector first.")
        return

    dot = build_diagram(records, gateway_ip=default_gateway_ip())
    out_path = dot.render(os.path.join(OUTPUT_DIR, "device_diagram"), cleanup=True)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
