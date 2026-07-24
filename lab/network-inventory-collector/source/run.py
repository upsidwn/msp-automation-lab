# Interactive multi-device inventory run. Prompts for one device
# (vendor + IP) at a time, shares a single credential pool across the
# whole run regardless of vendor, and asks whether to continue after
# each device. This is the manual stepping stone toward real
# auto-discovery (SNMP/LLDP sweep) -- see docs/ROADMAP.md. Swapping the
# "ask a human for the IP" step for an automatic one later is the only
# thing that changes; the shared pool + vendor dispatch + loop stay.

import json
import os

from dotenv import load_dotenv
from netmiko import NetmikoTimeoutException

import collector as junos_collector
from auth import connect_with_pool
from config import load_credential_pool

load_dotenv()

# device_type, label, collect(conn, host) -> record. None = not built yet.
VENDORS = {
    "1": ("juniper_junos", "Juniper (Junos)", junos_collector.collect),
    "2": ("extreme_exos", "Extreme (EXOS)", None),
}


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
        print("No collector built for that vendor yet -- skipping.")
        return prompt_device()

    host = input("Device IP/hostname: ").strip()
    return device_type, host, collect_fn


def main():
    pool = load_credential_pool()
    records = []

    while True:
        device_type, host, collect_fn = prompt_device()

        try:
            conn = connect_with_pool(device_type, host, pool)
        except NetmikoTimeoutException:
            print(f"Timed out connecting to {host} -- check it's reachable and SSH is enabled.")
        else:
            try:
                record = collect_fn(conn, host)
            finally:
                conn.disconnect()

            records.append(record)
            print(json.dumps(record, indent=2))

        again = input("\nAdd another device? (y/n): ").strip().lower()
        if again != "y":
            break

    out_path = os.path.join(os.path.dirname(__file__), "..", "examples", "inventory_run.json")
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)

    print(f"\nDone -- {len(records)} device(s) collected, written to {out_path}")


if __name__ == "__main__":
    main()
