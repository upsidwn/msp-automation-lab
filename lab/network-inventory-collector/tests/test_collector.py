import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from collector import COMMANDS, collect, parse_hardware, parse_interfaces, parse_version

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read_fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return f.read()


def test_parse_version():
    result = parse_version(_read_fixture("version.json"))

    assert result["vendor"] == "juniper"
    assert result["model"] == "lab-switch-1"
    assert result["firmware"] == "21.4R3.15"


def test_parse_hardware():
    result = parse_hardware(_read_fixture("hardware.json"))

    assert result["serial"] == "lab-switch-1-serial"


def test_parse_interfaces():
    interfaces = parse_interfaces(_read_fixture("interfaces.json"))

    assert len(interfaces) > 0
    assert all({"name", "admin_status", "oper_status", "ip_addresses"} <= iface.keys() for iface in interfaces)

    irb = next(iface for iface in interfaces if iface["name"] == "irb")
    assert "192.0.2.212/24" in irb["ip_addresses"]


def test_collect_builds_full_record_from_connection():
    fixtures_by_command = {
        COMMANDS["version"]: _read_fixture("version.json"),
        COMMANDS["hardware"]: _read_fixture("hardware.json"),
        COMMANDS["interfaces"]: _read_fixture("interfaces.json"),
    }

    fake_conn = MagicMock()
    fake_conn.send_command.side_effect = lambda cmd, read_timeout=None: fixtures_by_command[cmd]

    record = collect(fake_conn, "10.0.0.1")

    assert record["host"] == "10.0.0.1"
    assert record["vendor"] == "juniper"
    assert record["serial"] == "lab-switch-1-serial"
    assert "collected_at" in record
