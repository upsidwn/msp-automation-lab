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

import requests
from dotenv import load_dotenv

import collector as junos_collector
import collector_exos as exos_collector
import collector_unifi
from auth import try_ssh_device_types
from config import MissingConfigError, load_credential_pool, load_unifi_config
from nmap_scan import scan

load_dotenv()

SSH_COLLECTORS = {
    "juniper_junos": junos_collector.collect,
    "extreme_exos": exos_collector.collect,
}


def dispatch_ssh(host, pool):
    result = try_ssh_device_types(host, pool, list(SSH_COLLECTORS.keys()))
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


def discover(cidr):
    pool = load_credential_pool()

    try:
        unifi_config = load_unifi_config()
    except MissingConfigError:
        unifi_config = None

    candidates = scan(cidr)
    records = []
    unidentified = []

    for candidate in candidates:
        host = candidate["ip"]
        ports = {p["port"] for p in candidate["ports"]}
        found = False

        if 22 in ports:
            record = dispatch_ssh(host, pool)
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
            unidentified.append(candidate)
            print(f"?? {host} -- open ports {sorted(ports)}, could not identify/authenticate")

    return records, unidentified


def main():
    parser = argparse.ArgumentParser(
        description="Scan a subnet and auto-collect inventory from anything identifiable."
    )
    parser.add_argument("cidr", help="Target CIDR to scan, e.g. 192.168.1.0/24")
    args = parser.parse_args()

    try:
        records, unidentified = discover(args.cidr)
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
