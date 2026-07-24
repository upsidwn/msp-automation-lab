import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from collector_exos import (
    COMMANDS,
    collect,
    parse_ports,
    parse_switch,
    parse_version,
    parse_vlan_interfaces,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read_fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return f.read()


def test_parse_version():
    result = parse_version(_read_fixture("exos_version.txt"))

    assert result["firmware"] == "30.1.1.1"
    assert result["serial"] == "lab-switch-2-serial"


def test_parse_switch():
    result = parse_switch(_read_fixture("exos_switch.txt"))

    assert result["hostname"] == "lab-switch-2"
    assert result["vendor"] == "extreme"
    assert result["model"] == "lab-switch-2-SwitchEngine"


def test_parse_ports():
    interfaces = parse_ports(_read_fixture("exos_ports.txt"))

    assert len(interfaces) == 3
    assert all({"name", "admin_status", "oper_status", "ip_addresses"} <= i.keys() for i in interfaces)

    by_name = {i["name"]: i for i in interfaces}
    # Port 1: admin enabled, link active -> both up
    assert by_name["1"]["admin_status"] == "up"
    assert by_name["1"]["oper_status"] == "up"
    # Port 2: admin enabled, link ready (no cable) -> admin up, oper down
    assert by_name["2"]["admin_status"] == "up"
    assert by_name["2"]["oper_status"] == "down"
    # Port 3: admin disabled -> both down, proving these are independent now
    assert by_name["3"]["admin_status"] == "down"
    assert by_name["3"]["oper_status"] == "down"


def test_parse_vlan_interfaces():
    interfaces = parse_vlan_interfaces(_read_fixture("exos_vlan.txt"))

    assert len(interfaces) == 1
    assert interfaces[0]["name"] == "vlan-Default"
    assert interfaces[0]["ip_addresses"] == ["192.0.2.10/24"]


def test_collect_builds_full_record_from_connection():
    fixtures_by_command = {
        COMMANDS["version"]: _read_fixture("exos_version.txt"),
        COMMANDS["switch"]: _read_fixture("exos_switch.txt"),
        COMMANDS["ports"]: _read_fixture("exos_ports.txt"),
        COMMANDS["vlan"]: _read_fixture("exos_vlan.txt"),
    }

    fake_conn = MagicMock()
    fake_conn.send_command.side_effect = lambda cmd, read_timeout=None: fixtures_by_command[cmd]

    record = collect(fake_conn, "10.0.0.2")

    assert record["host"] == "10.0.0.2"
    assert record["vendor"] == "extreme"
    assert record["serial"] == "lab-switch-2-serial"
    assert len(record["interfaces"]) == 4  # 3 ports + 1 VLAN
    assert "collected_at" in record
