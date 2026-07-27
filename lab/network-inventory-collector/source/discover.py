# Orchestrates nmap-based discovery: scan a subnet, dispatch each
# candidate host through the existing vendor collectors based on which
# ports nmap found open. This is the actual "point it at a network"
# entry point -- unlike run.py, nothing prompts for an IP one at a time.
#
# Usage: python discover.py <cidr>, e.g. python discover.py 192.168.1.0/24

import argparse
import json
import os
import subprocess

import arp_lookup
import collector as junos_collector
import collector_exos as exos_collector
import collector_unifi
import mdns_discovery
import oui_lookup
import requests
from auth import prompt_and_retry_ssh, try_ssh_device_types
from config import MissingConfigError, load_credential_pool, load_unifi_config
from dotenv import load_dotenv
from nmap_scan import scan
from subnet_detect import SubnetDetectionError, detect_local_cidr

load_dotenv()

SSH_COLLECTORS = {
    "juniper_junos": junos_collector.collect,
    "extreme_exos": exos_collector.collect,
}


def dispatch_ssh(host, pool, prompt_on_auth_failure=False):
    result = try_ssh_device_types(host, pool, list(SSH_COLLECTORS.keys()))
    if result is None and prompt_on_auth_failure:
        result = prompt_and_retry_ssh(host, pool, list(SSH_COLLECTORS.keys()))
    if result is None:
        return None

    device_type, conn = result
    try:
        return SSH_COLLECTORS[device_type](conn, host)
    finally:
        conn.disconnect()


def dispatch_unifi(host, unifi_config):
    if unifi_config is None:
        return None

    try:
        return collector_unifi.collect_all(host, unifi_config["api_key"])
    except requests.exceptions.RequestException:
        return None


def enrich_unidentified(candidate):
    """Adds a MAC + manufacturer guess to a candidate we couldn't
    otherwise identify -- most valuable exactly here, since a fully
    identified Junos/EXOS/UniFi record already tells you the vendor
    from the device itself. Prefers nmap's own MAC when it has one,
    falls back to reading the OS's ARP cache (see arp_lookup.py for why
    that works without any elevated privileges).
    """
    mac = candidate["mac"] or arp_lookup.get_mac(candidate["ip"])
    vendor = oui_lookup.get_vendor(mac)

    return {**candidate, "mac": mac, "mac_vendor": vendor, "hostname": None, "services": []}


def _mdns_candidates(seconds):
    if seconds <= 0:
        return []
    return mdns_discovery.merge_by_ip(mdns_discovery.listen(duration=seconds))


def merge_mdns(records, unidentified, candidates):
    """Folds mDNS-only sightings into the existing results in place: skip
    an IP nmap already fully identified, add a hostname/services to an
    entry nmap saw but couldn't identify, or add a brand new unidentified
    entry for an IP nmap's active scan missed outright. That last case
    is the actual point of listening passively at all.
    """
    for candidate in candidates:
        ip = candidate["ip"]
        if any(r.get("host") == ip for r in records):
            continue

        existing = next((u for u in unidentified if u.get("ip") == ip), None)
        if existing is None:
            mac = arp_lookup.get_mac(ip)
            existing = {"ip": ip, "mac": mac, "mac_vendor": oui_lookup.get_vendor(mac)}
            unidentified.append(existing)

        existing["hostname"] = existing.get("hostname") or candidate["hostname"]
        existing["services"] = candidate["services"]

        services = ", ".join(candidate["services"]) or "none"
        print(f"   (mDNS) {ip}: {candidate['hostname'] or 'no hostname'}, services: {services}")


def discover(cidr, thorough=False, prompt_on_auth_failure=False, mdns_seconds=0):
    pool = load_credential_pool()

    try:
        unifi_config = load_unifi_config()
    except MissingConfigError:
        unifi_config = None

    candidates = scan(cidr, thorough=thorough)
    records = []
    unidentified = []

    for candidate in candidates:
        host = candidate["ip"]
        ports = {p["port"] for p in candidate["ports"]}
        found = False

        if 22 in ports:
            record = dispatch_ssh(host, pool, prompt_on_auth_failure=prompt_on_auth_failure)
            if record:
                records.append(record)
                print(f"OK: {host} -- {record['vendor']} {record.get('model')}")
                found = True

        if not found and 443 in ports:
            unifi_records = dispatch_unifi(host, unifi_config)
            if unifi_records:
                records.extend(unifi_records)
                print(f"OK: {host} -- unifi controller, {len(unifi_records)} device(s)")
                found = True

        if not found:
            entry = enrich_unidentified(candidate)
            unidentified.append(entry)
            vendor_hint = f", possibly {entry['mac_vendor']}" if entry["mac_vendor"] else ""
            print(f"?? {host} -- open ports {sorted(ports)}, could not identify/authenticate{vendor_hint}")

    try:
        mdns_candidates = _mdns_candidates(mdns_seconds)
        if mdns_candidates:
            merge_mdns(records, unidentified, mdns_candidates)
    except Exception as e:  # noqa: BLE001, untrusted device data, any exception type is possible
        print(f"mDNS listen failed, skipping it and keeping the active scan results: {e}")

    return records, unidentified


def main():
    parser = argparse.ArgumentParser(
        description="Scan a subnet and auto-collect inventory from anything identifiable."
    )
    parser.add_argument(
        "cidr",
        nargs="?",
        default=None,
        help=(
            "Target CIDR to scan, e.g. 192.168.1.0/24. If omitted, auto-detects "
            "the local machine's own subnet (the one its default route is on)."
        ),
    )
    parser.add_argument(
        "--thorough",
        action="store_true",
        help=(
            "Skip host-discovery entirely and port-scan every IP directly (nmap -Pn). "
            "Finds anything the fast default might miss, at real cost -- a single slow "
            "host can add minutes, not seconds. Use for a deliberate final pass, not routine runs."
        ),
    )
    parser.add_argument(
        "--prompt-on-auth-failure",
        action="store_true",
        help=(
            "When a host has SSH open but no pool credential works against any known "
            "vendor, pause and offer to enter credentials for it right there instead of "
            "silently marking it unidentified. Off by default -- a batch scan shouldn't "
            "stop for keyboard input unless asked to."
        ),
    )
    parser.add_argument(
        "--mdns-seconds",
        type=int,
        default=5,
        help=(
            "Seconds to passively listen for mDNS/DNS-SD announcements after the active "
            "scan finishes. Catches self-announcing devices (smart speakers, printers, "
            "IoT gear) that don't have SSH/HTTP/HTTPS open at all, so nmap's scan would "
            "never find them regardless of probe type. Zero elevated privileges needed. "
            "0 skips it entirely."
        ),
    )
    args = parser.parse_args()

    cidr = args.cidr
    if cidr is None:
        try:
            cidr = detect_local_cidr()
        except SubnetDetectionError as e:
            print(f"{e} Pass a CIDR explicitly, e.g. `python discover.py 192.168.1.0/24`.")
            return
        print(f"No CIDR given -- auto-detected local subnet: {cidr}")

    try:
        records, unidentified = discover(
            cidr,
            thorough=args.thorough,
            prompt_on_auth_failure=args.prompt_on_auth_failure,
            mdns_seconds=args.mdns_seconds,
        )
    except FileNotFoundError:
        print("nmap not found -- install it first (e.g. `brew install nmap` on macOS).")
        return
    except subprocess.CalledProcessError as e:
        print(f"nmap scan failed: {e}")
        return

    out_path = os.path.join(os.path.dirname(__file__), "..", "output", "discover_results.json")
    with open(out_path, "w") as f:
        json.dump({"records": records, "unidentified": unidentified}, f, indent=2)

    print(
        f"\nDone -- {len(records)} device(s) identified, {len(unidentified)} unidentified, "
        f"written to {out_path}"
    )


if __name__ == "__main__":
    main()
