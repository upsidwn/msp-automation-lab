# Standalone UniFi collector -- one console connection returns every
# adopted device in one shot, unlike collect.py/run.py's per-device SSH
# loop. See docs/ROADMAP.md and design-notes.md for why this is a
# separate code path from the Junos/EXOS collectors.

import json
import os

import requests
from dotenv import load_dotenv

from collector_unifi import collect_all
from config import MissingConfigError, load_unifi_config

load_dotenv()


def main():
    try:
        config = load_unifi_config()
    except MissingConfigError as e:
        print(f"Config error: {e}")
        return

    try:
        records = collect_all(config["host"], config["api_key"])
    except requests.exceptions.RequestException as e:
        print(f"Failed to reach UniFi console at {config['host']}: {e}")
        return

    for record in records:
        model = record.get("model") or "(unknown model)"
        print(f"OK: {record['hostname']} -- {record['vendor']} {model}")

    out_path = os.path.join(os.path.dirname(__file__), "..", "output", "unifi_inventory.json")
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)

    print(f"\nDone -- {len(records)} device(s) collected, written to {out_path}")


if __name__ == "__main__":
    main()
