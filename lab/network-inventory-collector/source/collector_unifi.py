# Pulls inventory from the UniFi Network Integration API -- a single
# call to the console returns every adopted device, unlike the
# per-device SSH collectors (collector.py, collector_exos.py) that need
# one connection per device. No serial number is exposed by this API;
# MAC address is kept as the stable per-device identifier instead.
# Interface detail is coarse (the API reports capability tags like
# "radios"/"ports", not per-port link state), so each device gets one
# "mgmt" interface entry carrying its own IP -- a known v1 simplification.

from datetime import datetime, timezone

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _get(host, api_key, path):
    url = f"https://{host}/proxy/network/integration/v1{path}"
    resp = requests.get(url, headers={"X-API-KEY": api_key}, verify=False, timeout=10)
    resp.raise_for_status()
    return resp.json()


def build_record(device, host):
    online = device.get("state") == "ONLINE"
    ip = device.get("ipAddress")

    return {
        "hostname": device.get("name"),
        "vendor": "unifi",
        "model": device.get("model"),
        "firmware": device.get("firmwareVersion"),
        "serial": None,
        "mac_address": device.get("macAddress"),
        "host": host,
        "interfaces": [
            {
                "name": "mgmt",
                "admin_status": "up" if online else "down",
                "oper_status": "up" if online else "down",
                "ip_addresses": [ip] if ip else [],
            }
        ],
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def collect_all(host, api_key):
    sites = _get(host, api_key, "/sites")["data"]

    records = []
    for site in sites:
        devices = _get(host, api_key, f"/sites/{site['id']}/devices")["data"]
        records.extend(build_record(device, host) for device in devices)

    return records
