import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from collector import parse_hardware, parse_interfaces, parse_version

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read_fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return f.read()


def test_parse_version():
    result = parse_version(_read_fixture("version.json"))

    assert result["vendor"] == "juniper"
    assert result["model"] == "ex4300-48p"
    assert result["firmware"] == "21.4R3.15"


def test_parse_hardware():
    result = parse_hardware(_read_fixture("hardware.json"))

    assert result["serial"] == "PD3716420189"


def test_parse_interfaces():
    interfaces = parse_interfaces(_read_fixture("interfaces.json"))

    assert len(interfaces) > 0
    assert all({"name", "admin_status", "oper_status", "ip_addresses"} <= iface.keys() for iface in interfaces)

    irb = next(iface for iface in interfaces if iface["name"] == "irb")
    assert "172.30.10.212/24" in irb["ip_addresses"]
