# Single entry point for every tool in this project. Prints a menu, asks
# which one to run, says what it needs first, then hands off to that
# tool's own CLI as a subprocess. Keeps this file simple, and each tool
# still works exactly the same if you run it directly instead.
#
# Adding a new tool later: one more entry in TOOLS, that's it.

import getpass
import json
import os
import subprocess
import sys

import keychain
from subnet_detect import SubnetDetectionError, detect_local_cidr

SOURCE_DIR = os.path.dirname(__file__)
DISCOVER_OUTPUT = os.path.join(SOURCE_DIR, "..", "output", "discover_results.json")


def _discover_args():
    try:
        detected = detect_local_cidr()
    except SubnetDetectionError as e:
        print(f"Could not auto-detect a subnet: {e}")
        cidr = input("Enter a CIDR to scan instead, e.g. 192.168.1.0/24: ").strip()
    else:
        use_detected = input(f"Auto-detected subnet: {detected}. Scan this (y/n)? ").strip().lower()
        cidr = detected if use_detected == "y" else input("Enter a CIDR to scan instead: ").strip()

    args = [cidr] if cidr else []

    thorough = input("Thorough mode, skip host-discovery and scan every IP directly (y/n): ").strip().lower()
    if thorough == "y":
        args.append("--thorough")

    prompt_fail = input("Prompt for credentials when auth fails instead of skipping (y/n): ").strip().lower()
    if prompt_fail == "y":
        args.append("--prompt-on-auth-failure")

    mdns_seconds = input(
        "Seconds to passively listen for mDNS announcements after the scan, 0 to skip (default 5): "
    ).strip()
    if mdns_seconds:
        args += ["--mdns-seconds", mdns_seconds]

    return args


def _run_args():
    has_list = input("Already have a list of devices to collect (y/n)? ").strip().lower()
    if has_list != "y":
        return []

    print("Format: a CSV file, one device per line, two columns: vendor,host")
    print("Vendor is 'juniper' or 'exos'. Example line: juniper,192.168.1.10")
    print("Real IPs, so put it in devices/ (gitignored), e.g. devices/mylist.csv")
    path = input("Path to that file: ").strip()

    return ["--devices-file", path] if path else []


def _filter_and_report(vendor):
    """The scan itself still finds everything; this just reads back what
    discover.py already wrote and prints only the one vendor's records,
    for a "just show me the X devices" menu option.
    """
    try:
        with open(DISCOVER_OUTPUT) as f:
            data = json.load(f)
    except FileNotFoundError:
        print("\nNo scan results found to filter.")
        return

    matches = [r for r in data.get("records", []) if r.get("vendor") == vendor]

    print(f"\n{vendor.capitalize()} devices found: {len(matches)}")
    for record in matches:
        model = record.get("model") or "(unknown model)"
        name = record.get("hostname") or record.get("host")
        print(f"  {name}, {model}")


def _collect_env():
    use_env = input("Use NIC_JUNOS_HOST and credentials from .env (y/n)? ").strip().lower()
    if use_env == "y":
        return {}

    host = input("Device IP/hostname: ").strip()

    saved = keychain.load_credential(host)
    if saved and input(f"Found a saved credential for {host}, use it (y/n)? ").strip().lower() == "y":
        return {"NIC_JUNOS_HOST": host, "NIC_CRED_1_USER": saved["username"], "NIC_CRED_1_PASS": saved["password"]}

    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    if input("Save this to your OS keychain for next time (y/n)? ").strip().lower() == "y":
        keychain.save_credential(host, {"username": username, "password": password})

    return {"NIC_JUNOS_HOST": host, "NIC_CRED_1_USER": username, "NIC_CRED_1_PASS": password}


def _collect_unifi_env():
    use_env = input("Use NIC_UNIFI_HOST and NIC_UNIFI_API_KEY from .env (y/n)? ").strip().lower()
    if use_env == "y":
        return {}

    host = input("UniFi console host/IP: ").strip()

    saved = keychain.load_credential(host)
    if saved and input(f"Found a saved credential for {host}, use it (y/n)? ").strip().lower() == "y":
        return {"NIC_UNIFI_HOST": host, "NIC_UNIFI_API_KEY": saved["api_key"]}

    api_key = getpass.getpass("API key: ")

    if input("Save this to your OS keychain for next time (y/n)? ").strip().lower() == "y":
        keychain.save_credential(host, {"api_key": api_key})

    return {"NIC_UNIFI_HOST": host, "NIC_UNIFI_API_KEY": api_key}


TOOLS = [
    {
        "label": "Auto-discover a subnet (nmap scan, dispatches each device to the right collector)",
        "script": "discover.py",
        "needs": "nmap installed; credentials in .env for anything it finds with SSH open",
        "build_args": _discover_args,
    },
    {
        "label": "Scan for Extreme EXOS devices only (same subnet scan, filtered afterward)",
        "script": "discover.py",
        "needs": "nmap installed; credentials in .env for anything it finds with SSH open",
        "build_args": _discover_args,
        "after_run": lambda: _filter_and_report("extreme"),
    },
    {
        "label": "Manual multi-device collection (type devices in, or point at a list)",
        "script": "run.py",
        "needs": "credentials in .env, or type them in when it asks",
        "build_args": _run_args,
    },
    {
        "label": "Single Juniper device (quick one-off collection)",
        "script": "collect.py",
        "needs": "NIC_JUNOS_HOST and credentials, either from .env or entered here",
        "build_args": list,
        "build_env": _collect_env,
    },
    {
        "label": "UniFi controller (pulls every adopted device in one call)",
        "script": "collect_unifi.py",
        "needs": "NIC_UNIFI_HOST and NIC_UNIFI_API_KEY, either from .env or entered here",
        "build_args": list,
        "build_env": _collect_unifi_env,
    },
    {
        "label": "Firmware inventory + compliance report (reads what's already collected, no new scan)",
        "script": "firmware_report.py",
        "needs": "nothing extra; reads output/ from previous runs, checks known_good_firmware.json",
        "build_args": list,
    },
    {
        "label": "Device diagram (reads what's already collected, no new scan)",
        "script": "diagram.py",
        "needs": "graphviz installed (brew install graphviz); reads output/ from previous runs",
        "build_args": list,
    },
]


def print_menu():
    print("\nNetwork Inventory Collector, pick a tool:\n")
    for i, tool in enumerate(TOOLS, start=1):
        print(f"  {i}) {tool['label']}")
    print("  q) Quit")


def prompt_choice():
    choice = input("\nChoice: ").strip().lower()
    if choice == "q":
        return None

    if not choice.isdigit() or not (1 <= int(choice) <= len(TOOLS)):
        print("Not a valid choice, try again.")
        return prompt_choice()

    return TOOLS[int(choice) - 1]


def run_tool(tool):
    print(f"\nNeeds: {tool['needs']}")
    args = tool["build_args"]()
    extra_env = tool.get("build_env", dict)()
    env = {**os.environ, **extra_env}

    script_path = os.path.join(SOURCE_DIR, tool["script"])
    subprocess.run([sys.executable, script_path] + args, env=env, check=False)

    after_run = tool.get("after_run")
    if after_run:
        after_run()


def main():
    while True:
        print_menu()
        tool = prompt_choice()
        if tool is None:
            break

        run_tool(tool)

        again = input("\nRun another tool? (y/n): ").strip().lower()
        if again != "y":
            break


if __name__ == "__main__":
    main()
