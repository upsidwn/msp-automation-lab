# Real Juniper inventory collector -- connects, gathers version/hardware/
# interface data, writes a JSON record (and a flattened CSV summary line)
# to examples/. connect_test.py stays as the quick raw-connectivity check.

import csv
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from netmiko import NetmikoTimeoutException

from auth import connect_with_pool
from collector import parse_hardware, parse_interfaces, parse_version
from config import MissingConfigError, load_credential_pool, load_juniper_host

load_dotenv()

COMMANDS = {
    "version": "show version | display json",
    "hardware": "show chassis hardware | display json",
    "interfaces": "show interfaces terse | display json",
}


def collect_juniper():
    host = load_juniper_host()
    pool = load_credential_pool()

    conn = connect_with_pool("juniper_junos", host, pool)
    try:
        raw = {key: conn.send_command(cmd, read_timeout=30) for key, cmd in COMMANDS.items()}
    finally:
        conn.disconnect()

    record = parse_version(raw["version"])
    record["serial"] = parse_hardware(raw["hardware"])["serial"]
    record["interfaces"] = parse_interfaces(raw["interfaces"])
    record["collected_at"] = datetime.now(timezone.utc).isoformat()

    return record


def write_json(record, path):
    with open(path, "w") as f:
        json.dump(record, f, indent=2)


def write_csv_summary(record, path):
    fieldnames = ["hostname", "vendor", "model", "serial", "firmware", "interface_count", "collected_at"]
    row = {
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
