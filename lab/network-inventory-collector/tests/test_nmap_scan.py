import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from nmap_scan import parse_xml

# Inline sample rather than a fixture file -- unlike the vendor collectors,
# nmap doesn't need specific hardware to test against (anyone running this
# has a network to scan), so there's no real-world fixture to sanitize here.
# This just keeps parse_xml() covered by a fast, deterministic test.
SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nmaprun>
<nmaprun scanner="nmap" args="nmap -sT -sV --open -p 22,80,443 -oX - 192.0.2.0/24" version="7.99">
<scaninfo type="connect" protocol="tcp" numservices="3" services="22,80,443"/>
<host starttime="0" endtime="0">
<status state="up" reason="syn-ack" reason_ttl="0"/>
<address addr="192.0.2.10" addrtype="ipv4"/>
<address addr="00:11:22:33:44:55" addrtype="mac" vendor="Lab Vendor"/>
<hostnames></hostnames>
<ports>
<extraports state="filtered" count="1">
<extrareasons reason="no-response" count="1" proto="tcp" ports="443"/>
</extraports>
<port protocol="tcp" portid="22"><state state="open" reason="syn-ack" reason_ttl="0"/><service name="ssh" product="OpenSSH" version="8.1" extrainfo="protocol 2.0" method="probed" conf="10"/></port>
<port protocol="tcp" portid="80"><state state="open" reason="syn-ack" reason_ttl="0"/><service name="http" product="CherryPy wsgiserver" method="probed" conf="10"/></port>
</ports>
<times srtt="1000" rttvar="1000" to="100000"/>
</host>
<host starttime="0" endtime="0">
<status state="up" reason="syn-ack" reason_ttl="0"/>
<address addr="192.0.2.11" addrtype="ipv4"/>
<hostnames></hostnames>
<ports>
<extraports state="filtered" count="2">
<extrareasons reason="no-response" count="2" proto="tcp" ports="22,80"/>
</extraports>
<port protocol="tcp" portid="443"><state state="open" reason="syn-ack" reason_ttl="0"/><service name="https" product="nginx" version="1.25" method="probed" conf="10"/></port>
</ports>
<times srtt="1000" rttvar="1000" to="100000"/>
</host>
<runstats><finished time="0" timestr="" summary="" elapsed="1.0" exit="success"/><hosts up="2" down="0" total="2"/>
</runstats>
</nmaprun>
"""


def test_parse_xml_returns_one_candidate_per_host():
    candidates = parse_xml(SAMPLE_XML)

    assert len(candidates) == 2
    assert {c["ip"] for c in candidates} == {"192.0.2.10", "192.0.2.11"}


def test_parse_xml_includes_mac_when_present():
    candidates = parse_xml(SAMPLE_XML)

    by_ip = {c["ip"]: c for c in candidates}
    assert by_ip["192.0.2.10"]["mac"] == "00:11:22:33:44:55"


def test_parse_xml_mac_is_none_when_absent():
    candidates = parse_xml(SAMPLE_XML)

    by_ip = {c["ip"]: c for c in candidates}
    assert by_ip["192.0.2.11"]["mac"] is None


def test_parse_xml_extracts_open_ports_and_service_info():
    candidates = parse_xml(SAMPLE_XML)

    by_ip = {c["ip"]: c for c in candidates}
    ports = by_ip["192.0.2.10"]["ports"]

    assert len(ports) == 2
    ssh = next(p for p in ports if p["port"] == 22)
    assert ssh["service"] == "ssh"
    assert ssh["product"] == "OpenSSH"
    assert ssh["version"] == "8.1"


def test_parse_xml_handles_missing_version():
    candidates = parse_xml(SAMPLE_XML)

    by_ip = {c["ip"]: c for c in candidates}
    http = next(p for p in by_ip["192.0.2.10"]["ports"] if p["port"] == 80)

    assert http["version"] is None
