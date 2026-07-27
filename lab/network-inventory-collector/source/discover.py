# Orchestrates nmap-based discovery: scan a subnet, dispatch each
# candidate host through the existing vendor collectors based on which
# ports nmap found open. This is the actual "point it at a network"
# entry point -- unlike run.py, nothing prompts for an IP one at a time.
#
# Usage: python discover.py <cidr>, e.g. python discover.py 192.168.1.0/24

import argparse
import ipaddress
import json
import os
import subprocess

import arp_lookup
import arp_scan
import collector as junos_collector
import collector_exos as exos_collector
import collector_unifi
import mdns_discovery
import oui_lookup
import requests
from auth import prompt_and_retry_ssh, try_ssh_device_types
from config import MissingConfigError, load_credential_pool, load_unifi_config
from dotenv import load_dotenv
from live_table import LiveTable
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


def _in_cidr(ip, network):
    try:
        return ipaddress.ip_address(ip) in network
    except ValueError:
        return False


def _mdns_candidates(seconds, cidr, records, table):
    """Live-updates the table as services resolve during the listen
    window, skipping any IP already fully identified by nmap (same rule
    merge_mdns applies to the data) so an identified device's row
    doesn't pick up mDNS info nobody asked to see there. Tracks which
    IPs got a live update so merge_mdns doesn't redraw the same row a
    second time right after.

    Confirmed live: mDNS is a passive listen with no concept of subnet
    boundaries at all, so on a flat network bigger than the requested
    CIDR it happily reports devices way outside it. Filtered to cidr
    here so results stay scoped to what was actually asked for, same as
    nmap's own results already are just by construction.
    """
    if seconds <= 0:
        return [], set()

    network = ipaddress.ip_network(cidr, strict=False)
    seen_live = set()

    def on_update(candidate):
        ip = candidate["ip"]
        if not _in_cidr(ip, network):
            return
        if any(r.get("host") == ip for r in records):
            return
        table.upsert(ip, hostname=candidate["hostname"], services=candidate["services"])
        seen_live.add(ip)

    candidates = mdns_discovery.merge_by_ip(mdns_discovery.listen(duration=seconds, on_update=on_update))
    candidates = [c for c in candidates if _in_cidr(c["ip"], network)]
    return candidates, seen_live


def merge_mdns(records, unidentified, candidates, table, seen_live=frozenset()):
    """Folds mDNS-only sightings into the existing results in place: skip
    an IP nmap already fully identified, add a hostname/services to an
    entry nmap saw but couldn't identify, or add a brand new unidentified
    entry for an IP nmap's active scan missed outright. That last case
    is the actual point of listening passively at all. Also the
    guaranteed path to the live table for candidates _mdns_candidates
    didn't already show live (seen_live), so nothing's missing from the
    display even if timing didn't line up.
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

        if ip not in seen_live:
            table.upsert(ip, hostname=candidate["hostname"], services=candidate["services"])


def _arp_candidates(enabled, cidr, records, table):
    """Same shape as _mdns_candidates: streams live table updates as
    arp-scan reports hosts, skips anything nmap already identified, and
    tracks which IPs were shown live so merge_arp doesn't repeat them.
    arp-scan is already told to scan cidr specifically, but it can still
    answer for something just outside it on the same physical segment,
    so results get the same CIDR filter mDNS needs.
    """
    if not enabled:
        return [], set()

    network = ipaddress.ip_network(cidr, strict=False)
    seen_live = set()

    def on_found(candidate):
        ip = candidate["ip"]
        if not _in_cidr(ip, network):
            return
        if any(r.get("host") == ip for r in records):
            return
        table.upsert(ip, mac=candidate["mac"], mac_vendor=candidate["vendor"])
        seen_live.add(ip)

    candidates = arp_scan.scan(cidr, on_found=on_found) or []
    candidates = [c for c in candidates if _in_cidr(c["ip"], network)]
    return candidates, seen_live


def merge_arp(records, unidentified, candidates, table, seen_live=frozenset()):
    """Folds ARP-only sightings into the existing results in place, the
    same shape merge_mdns already uses: skip an IP nmap already fully
    identified, fill in a mac/vendor an entry nmap saw but couldn't
    identify was missing, or add a brand new unidentified entry for an
    IP nmap's active scan missed outright. Answering ARP needs no open
    port at all, so this catches devices nmap can't find no matter which
    probe type it uses. Also the guaranteed path to the live table for
    candidates _arp_candidates didn't already show live (the sudo-
    elevated retry doesn't stream on_found, so everything from that path
    lands here instead).
    """
    for candidate in candidates:
        ip = candidate["ip"]
        if any(r.get("host") == ip for r in records):
            continue

        existing = next((u for u in unidentified if u.get("ip") == ip), None)
        if existing is None:
            existing = {
                "ip": ip,
                "mac": candidate["mac"],
                "mac_vendor": candidate["vendor"],
                "hostname": None,
                "services": [],
            }
            unidentified.append(existing)
        else:
            existing["mac"] = existing.get("mac") or candidate["mac"]
            existing["mac_vendor"] = existing.get("mac_vendor") or candidate["vendor"]

        if ip not in seen_live:
            table.upsert(ip, mac=candidate["mac"], mac_vendor=candidate["vendor"])


def discover(cidr, thorough=False, prompt_on_auth_failure=False, mdns_seconds=0, arp_sweep=False, table=None):
    table = table or LiveTable()
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
        table.upsert(host, status="scanning...")
        ports = {p["port"] for p in candidate["ports"]}
        found = False

        if 22 in ports:
            record = dispatch_ssh(host, pool, prompt_on_auth_failure=prompt_on_auth_failure)
            if record:
                records.append(record)
                table.upsert(host, status="", vendor=record["vendor"], model=record.get("model"))
                found = True

        if not found and 443 in ports:
            unifi_records = dispatch_unifi(host, unifi_config)
            if unifi_records:
                records.extend(unifi_records)
                table.upsert(host, status="", vendor="unifi", model=f"{len(unifi_records)} device(s)")
                found = True

        if not found:
            entry = enrich_unidentified(candidate)
            unidentified.append(entry)
            status = "unidentified" if entry["mac_vendor"] else "unidentified, no vendor guess"
            table.upsert(host, status=status, mac_vendor=entry["mac_vendor"])

    try:
        mdns_candidates, seen_live_mdns = _mdns_candidates(mdns_seconds, cidr, records, table)
        if mdns_candidates:
            merge_mdns(records, unidentified, mdns_candidates, table, seen_live_mdns)
    except Exception as e:  # noqa: BLE001, untrusted device data, any exception type is possible
        print(f"mDNS listen failed, skipping it and keeping the active scan results: {e}")

    try:
        candidates_arp, seen_live_arp = _arp_candidates(arp_sweep, cidr, records, table)
        if candidates_arp:
            merge_arp(records, unidentified, candidates_arp, table, seen_live_arp)
    except Exception as e:  # noqa: BLE001, several failure modes here, all should degrade the same way
        print(f"ARP sweep failed, skipping it and keeping the results so far: {e}")

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
    parser.add_argument(
        "--arp-sweep",
        action="store_true",
        help=(
            "Send ARP requests across the subnet, catches live hosts that don't answer "
            "on any of nmap's probed ports at all (no open port needed to answer ARP). "
            "Needs arp-scan installed. Tries without elevated privileges first, only "
            "prompts for sudo if that fails. Off by default since it needs a real "
            "opt-in for anything that might ask for a password."
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
    else:
        try:
            ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            print(f"'{cidr}' isn't a valid CIDR or IP, e.g. 192.168.1.0/24.")
            return

    try:
        records, unidentified = discover(
            cidr,
            thorough=args.thorough,
            prompt_on_auth_failure=args.prompt_on_auth_failure,
            mdns_seconds=args.mdns_seconds,
            arp_sweep=args.arp_sweep,
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
