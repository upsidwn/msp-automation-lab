import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from dynamic_inventory import build_inventory, load_records

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "source", "dynamic_inventory.py")


def _record(vendor, host, hostname=None):
    return {"vendor": vendor, "host": host, "hostname": hostname, "model": "some-model"}


def test_load_records_returns_empty_when_file_missing(tmp_path):
    records = load_records(str(tmp_path / "nope.json"))

    assert records == []


def test_load_records_returns_empty_on_malformed_json(tmp_path):
    bad_file = tmp_path / "discover_results.json"
    bad_file.write_text("not valid json {{{")

    records = load_records(str(bad_file))

    assert records == []


def test_load_records_reads_records_key(tmp_path):
    discover_file = tmp_path / "discover_results.json"
    discover_file.write_text(json.dumps({
        "records": [_record("juniper", "10.0.0.1")],
        "unidentified": [{"ip": "10.0.0.99"}],
    }))

    records = load_records(str(discover_file))

    assert len(records) == 1
    assert records[0]["host"] == "10.0.0.1"


def test_build_inventory_groups_by_vendor():
    records = [
        _record("juniper", "10.0.0.1", hostname="sw1"),
        _record("extreme", "10.0.0.2", hostname="sw2"),
    ]

    inventory = build_inventory(records)

    assert inventory["junos"]["hosts"] == ["sw1"]
    assert inventory["exos"]["hosts"] == ["sw2"]
    assert inventory["_meta"]["hostvars"]["sw1"]["ansible_host"] == "10.0.0.1"
    assert inventory["_meta"]["hostvars"]["sw2"]["ansible_host"] == "10.0.0.2"


def test_build_inventory_skips_unifi_and_unidentified_vendors():
    records = [
        _record("unifi", "10.0.0.3", hostname="ap1"),
        _record("some_unknown_vendor", "10.0.0.4", hostname="mystery"),
    ]

    inventory = build_inventory(records)

    assert inventory["junos"]["hosts"] == []
    assert inventory["exos"]["hosts"] == []
    assert "ap1" not in inventory["_meta"]["hostvars"]
    assert "mystery" not in inventory["_meta"]["hostvars"]


def test_build_inventory_falls_back_to_host_when_hostname_missing():
    records = [_record("juniper", "10.0.0.1", hostname=None)]

    inventory = build_inventory(records)

    assert inventory["junos"]["hosts"] == ["10.0.0.1"]
    assert inventory["_meta"]["hostvars"]["10.0.0.1"]["ansible_host"] == "10.0.0.1"


def test_build_inventory_never_duplicates_a_host_entry():
    records = [
        _record("juniper", "10.0.0.1", hostname="sw1"),
        _record("juniper", "10.0.0.1", hostname="sw1"),
    ]

    inventory = build_inventory(records)

    assert inventory["junos"]["hosts"] == ["sw1"]


def test_script_list_output_is_valid_json_when_no_discover_output(tmp_path):
    env = dict(os.environ, NIC_DISCOVER_OUTPUT=str(tmp_path / "nope.json"))

    result = subprocess.run(
        [sys.executable, SCRIPT_PATH, "--list"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["junos"]["hosts"] == []
    assert data["exos"]["hosts"] == []


def test_script_host_flag_returns_empty_dict(tmp_path):
    env = dict(os.environ, NIC_DISCOVER_OUTPUT=str(tmp_path / "nope.json"))

    result = subprocess.run(
        [sys.executable, SCRIPT_PATH, "--host", "sw1"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {}
