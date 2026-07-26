# Prints every device's firmware version from whatever's already been
# collected in output/ (discover_results.json, inventory_run.json,
# juniper_inventory.json, unifi_inventory.json, whatever's actually
# there). No new device connections, no known-good version comparison
# yet, just a clean list to review. Saves to a file only if asked.

import csv
import glob
import json
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


def _records_from_file(path):
    with open(path) as f:
        data = json.load(f)

    if isinstance(data, dict) and "records" in data:
        return data["records"]
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def _dedupe_key(record):
    # mac_address is the only stable per-device identifier UniFi gives us
    # (every device from one controller shares the same "host" value,
    # the controller's own address, not a per-device one). host works
    # fine for the SSH vendors, where it's the actual device IP.
    return (record.get("vendor"), record.get("mac_address") or record.get("host") or record.get("hostname"))


def load_all_records(output_dir=OUTPUT_DIR):
    """Combines every *.json file already sitting in output_dir into one
    deduped list. The same device can show up in more than one file (a
    single-device collect.py run, then a later discover.py sweep) --
    whichever has the newer collected_at wins.
    """
    best = {}
    for path in sorted(glob.glob(os.path.join(output_dir, "*.json"))):
        for record in _records_from_file(path):
            key = _dedupe_key(record)
            existing = best.get(key)
            if existing is None or (record.get("collected_at") or "") > (existing.get("collected_at") or ""):
                best[key] = record

    return list(best.values())


def print_report(records):
    if not records:
        print("No collected inventory found in output/, run a collector first.")
        return

    rows = [
        (
            r.get("vendor") or "",
            r.get("hostname") or r.get("host") or "",
            r.get("model") or "",
            r.get("firmware") or "",
        )
        for r in records
    ]
    headers = ("VENDOR", "HOST", "MODEL", "FIRMWARE")
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(headers)]

    def _fmt(row):
        return "  ".join(val.ljust(width) for val, width in zip(row, widths))

    print(f"\nFirmware inventory ({len(records)} device(s)):\n")
    print(_fmt(headers))
    print(_fmt(["-" * w for w in widths]))
    for row in rows:
        print(_fmt(row))


def write_csv(records, path):
    fieldnames = ["vendor", "host", "hostname", "model", "firmware", "serial", "collected_at"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow({name: r.get(name, "") for name in fieldnames})


def main():
    records = load_all_records()
    print_report(records)

    if not records:
        return

    save = input("\nSave this to a file? (y/n): ").strip().lower()
    if save != "y":
        return

    out_path = os.path.join(OUTPUT_DIR, "firmware_report.csv")
    write_csv(records, out_path)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
