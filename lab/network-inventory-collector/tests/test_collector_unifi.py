import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from collector_unifi import build_record, collect_all

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read_fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


def test_build_record_online_device():
    device = _read_fixture("unifi_devices.json")["data"][0]

    record = build_record(device, "192.0.2.1")

    assert record["hostname"] == "lab-ap-1"
    assert record["vendor"] == "unifi"
    assert record["model"] == "U6 Lite"
    assert record["firmware"] == "6.7.54"
    assert record["serial"] is None
    assert record["mac_address"] == "00:11:22:33:44:01"
    assert record["interfaces"] == [
        {
            "name": "mgmt",
            "admin_status": "up",
            "oper_status": "up",
            "ip_addresses": ["192.0.2.11"],
        }
    ]


def test_build_record_offline_device():
    device = _read_fixture("unifi_devices.json")["data"][2]

    record = build_record(device, "192.0.2.1")

    assert record["interfaces"][0]["admin_status"] == "down"
    assert record["interfaces"][0]["oper_status"] == "down"


def test_collect_all_aggregates_across_sites():
    sites_response = MagicMock()
    sites_response.json.return_value = _read_fixture("unifi_sites.json")
    sites_response.raise_for_status.return_value = None

    devices_response = MagicMock()
    devices_response.json.return_value = _read_fixture("unifi_devices.json")
    devices_response.raise_for_status.return_value = None

    with patch("collector_unifi.requests.get", side_effect=[sites_response, devices_response]) as mock_get:
        records = collect_all("192.0.2.1", "fake-api-key")

    assert len(records) == 3
    assert {r["hostname"] for r in records} == {"lab-ap-1", "lab-switch-3", "lab-gateway-1"}

    # Confirm the API key was sent as the expected header.
    _, kwargs = mock_get.call_args_list[0]
    assert kwargs["headers"] == {"X-API-KEY": "fake-api-key"}
