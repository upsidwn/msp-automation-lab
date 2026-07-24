import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from nmap_scan import parse_xml

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read_fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return f.read()


def test_parse_xml_returns_one_candidate_per_host():
    candidates = parse_xml(_read_fixture("nmap_scan_sample.xml"))

    assert len(candidates) == 2
    assert {c["ip"] for c in candidates} == {"192.0.2.10", "192.0.2.11"}


def test_parse_xml_includes_mac_when_present():
    candidates = parse_xml(_read_fixture("nmap_scan_sample.xml"))

    by_ip = {c["ip"]: c for c in candidates}
    assert by_ip["192.0.2.10"]["mac"] == "00:11:22:33:44:55"


def test_parse_xml_mac_is_none_when_absent():
    candidates = parse_xml(_read_fixture("nmap_scan_sample.xml"))

    by_ip = {c["ip"]: c for c in candidates}
    assert by_ip["192.0.2.11"]["mac"] is None


def test_parse_xml_extracts_open_ports_and_service_info():
    candidates = parse_xml(_read_fixture("nmap_scan_sample.xml"))

    by_ip = {c["ip"]: c for c in candidates}
    ports = by_ip["192.0.2.10"]["ports"]

    assert len(ports) == 2
    ssh = next(p for p in ports if p["port"] == 22)
    assert ssh["service"] == "ssh"
    assert ssh["product"] == "OpenSSH"
    assert ssh["version"] == "8.1"


def test_parse_xml_handles_missing_version():
    candidates = parse_xml(_read_fixture("nmap_scan_sample.xml"))

    by_ip = {c["ip"]: c for c in candidates}
    http = next(p for p in by_ip["192.0.2.10"]["ports"] if p["port"] == 80)

    assert http["version"] is None
