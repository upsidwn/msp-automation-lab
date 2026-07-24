# Real Juniper inventory collector -- connects, gathers version/hardware/
# interface data, writes a JSON record (and a flattened CSV summary line)
# to examples/. connect_test.py stays as the quick raw-connectivity check.
# run.py is the multi-device version of this same collection logic.

import csv
import json
import os

from dotenv import load_dotenv
from netmiko import NetmikoTimeoutException

from auth import connect_with_pool
from collector import collect as collect_from_connection
from config import MissingConfigError, load_credential_pool, load_juniper_host

load_dotenv()


def collect_juniper():
    host = load_juniper_host()
    pool = load_credential_pool()

    conn = connect_with_pool("juniper_junos", host, pool)
    try:
        return collect_from_connection(conn, host)
    finally:
        conn.disconnect()


def write_json(record, path):
    with open(path, "w") as f:
        json.dump(record, f, indent=2)


def write_csv_summary(record, path):
    fieldnames = ["host", "hostname", "vendor", "model", "serial", "firmware", "interface_count", "collected_at"]
    row = {
        "host": record.get("host"),
        "hostname": record.get("hostname"),
        "vendor": record.get("vendor"),
        "model": record.get("model"),
        "serial": record.get("serial"),
        "firmware": record.get("firmware"),
        "interface_count": len(record.get("interfaces", [])),
        "collected_at": record.get("collected_at"),
    }

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def main():
    try:
        record = collect_juniper()
    except MissingConfigError as e:
        print(f"Config error: {e}")
        return
    except NetmikoTimeoutException:
        print("Timed out connecting -- check the device is reachable and SSH is enabled.")
        return

    out_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
    write_json(record, os.path.join(out_dir, "juniper_inventory.json"))
    write_csv_summary(record, os.path.join(out_dir, "juniper_inventory.csv"))

    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
