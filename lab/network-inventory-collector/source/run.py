# Multi-device inventory run for the SSH vendors, sharing one credential
# pool across the whole run regardless of vendor. Two ways to feed it a
# device list: type each one in as you go (the original manual stepping
# stone toward auto-discovery, see docs/ROADMAP.md), or point it at a
# simple CSV file with --devices-file if you already have the list.

import argparse
import csv
import json
import os

import collector as junos_collector
import collector_exos as exos_collector
from auth import connect_with_pool
from config import load_credential_pool
from dotenv import load_dotenv
from netmiko import NetmikoTimeoutException

load_dotenv()

# device_type, label, collect(conn, host) -> record. None = not built yet.
VENDOR_BY_NAME = {
    "juniper": ("juniper_junos", "Juniper (Junos)", junos_collector.collect),
    "exos": ("extreme_exos", "Extreme (EXOS)", exos_collector.collect),
}

# Same vendors, keyed by menu choice number for the interactive prompt.
VENDORS = {str(i): v for i, v in enumerate(VENDOR_BY_NAME.values(), start=1)}


def prompt_device():
    print("\nVendor:")
    for key, (_, label, _) in VENDORS.items():
        print(f"  {key}) {label}")

    choice = input("Select vendor: ").strip()
    if choice not in VENDORS:
        print("Unknown selection, try again.")
        return prompt_device()

    device_type, _, collect_fn = VENDORS[choice]
    if collect_fn is None:
        print("No collector built for that vendor yet, skipping.")
        return prompt_device()

    host = input("Device IP/hostname: ").strip()
    return device_type, host, collect_fn


def load_devices_file(path):
    """Reads a simple device list: one "vendor,host" pair per line,
    vendor is "juniper" or "exos" (case-insensitive). A header row is
    fine too, it just gets skipped since "vendor" itself isn't a
    recognized vendor name.
    """
    devices = []
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            vendor_name = row[0].strip().lower()
            if vendor_name not in VENDOR_BY_NAME:
                continue
            devices.append((vendor_name, row[1].strip()))

    return devices


def collect_one(device_type, host, collect_fn, pool):
    try:
        conn = connect_with_pool(device_type, host, pool)
    except NetmikoTimeoutException:
        print(f"Timed out connecting to {host}, check it's reachable and SSH is enabled.")
        return None

    try:
        return collect_fn(conn, host)
    finally:
        conn.disconnect()


def _report(host, record):
    model = record.get("model") or "(unknown model)"
    print(f"OK: {host}, {record['vendor']} {model}, {len(record['interfaces'])} interfaces")


def main():
    parser = argparse.ArgumentParser(description="Collect inventory from Juniper/EXOS devices.")
    parser.add_argument(
        "--devices-file",
        help=(
            "CSV file of vendor,host pairs to collect without prompting for each one "
            "(vendor is 'juniper' or 'exos'). Omit to be prompted interactively instead."
        ),
    )
    args = parser.parse_args()

    pool = load_credential_pool()
    records = []

    if args.devices_file:
        for vendor_name, host in load_devices_file(args.devices_file):
            device_type, _, collect_fn = VENDOR_BY_NAME[vendor_name]
            record = collect_one(device_type, host, collect_fn, pool)
            if record:
                records.append(record)
                _report(host, record)
    else:
        while True:
            device_type, host, collect_fn = prompt_device()
            record = collect_one(device_type, host, collect_fn, pool)
            if record:
                records.append(record)
                _report(host, record)

            again = input("\nAdd another device? (y/n): ").strip().lower()
            if again != "y":
                break

    out_path = os.path.join(os.path.dirname(__file__), "..", "output", "inventory_run.json")
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)

    print(f"\nDone, {len(records)} device(s) collected, written to {out_path}")


if __name__ == "__main__":
    main()
