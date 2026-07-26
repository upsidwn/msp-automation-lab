import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from diagram import _find_gateway_record, build_diagram, default_gateway_ip, main


def _record(vendor, host, model, hostname=None):
    return {"vendor": vendor, "host": host, "hostname": hostname, "model": model}


def _unifi_record(controller_host, own_ip, model, hostname):
    # UniFi's top-level "host" is the controller's address, shared by
    # every device behind it. Each device's own real IP lives on its
    # interfaces instead, matching collector_unifi.py's actual shape.
    return {
        "vendor": "unifi",
        "host": controller_host,
        "hostname": hostname,
        "model": model,
        "interfaces": [{"name": "mgmt", "ip_addresses": [own_ip]}],
    }


def test_build_diagram_adds_one_node_per_device():
    records = [
        _record("juniper", "10.0.0.1", "ex4300", hostname="sw1"),
        _record("extreme", "10.0.0.2", "x440"),
    ]

    dot = build_diagram(records)
    source = dot.source

    assert "sw1" in source
    assert "10.0.0.2" in source
    assert source.count("--") == 2


def test_build_diagram_uses_gateway_record_as_hub():
    records = [
        _record("unifi", "10.0.0.1", "UDM Pro", hostname="Dream-Machine"),
        _record("juniper", "10.0.0.2", "ex4300", hostname="sw1"),
    ]

    dot = build_diagram(records, gateway_ip="10.0.0.1")
    source = dot.source

    assert "Dream-Machine" in source
    assert "(gateway)" in source
    assert source.count("--") == 1


def test_build_diagram_disambiguates_unifi_gateway_when_host_shared_by_all():
    # Real quirk: the controller's shared host value happens to equal
    # the LAN gateway IP, so every device behind it matches by host
    # alone. The console's own interface IP is its WAN address (not
    # the gateway IP), so only its model name identifies it as the hub.
    records = [
        _unifi_record("192.0.2.1", "192.0.2.50", "U6-Lite", "AP-LivingRoom"),
        _unifi_record("192.0.2.1", "203.0.113.9", "UDM Pro", "Dream-Machine"),
        _unifi_record("192.0.2.1", "192.0.2.51", "USW Flex", "Switch-Garage"),
    ]

    dot = build_diagram(records, gateway_ip="192.0.2.1")
    source = dot.source

    # Assert the hub label directly, not just independent substring
    # presence elsewhere in the graph: an arbitrary/wrong pick among the
    # three shared-host candidates would still satisfy separate "in
    # source" checks on both strings, so pin them together as one label.
    assert "Dream-Machine\nUDM Pro (gateway)" in source
    assert "AP-LivingRoom" in source
    assert source.count("--") == 2


def test_find_gateway_record_picks_the_console_not_the_first_shared_host_match():
    # Same scenario as above, unit-tested directly against the picked
    # record rather than the rendered graph text.
    records = [
        _unifi_record("192.0.2.1", "192.0.2.50", "U6-Lite", "AP-LivingRoom"),
        _unifi_record("192.0.2.1", "203.0.113.9", "UDM Pro", "Dream-Machine"),
        _unifi_record("192.0.2.1", "192.0.2.51", "USW Flex", "Switch-Garage"),
    ]

    result = _find_gateway_record(records, "192.0.2.1")

    assert result is not None
    assert result["hostname"] == "Dream-Machine"


def test_build_diagram_falls_back_when_no_unifi_candidate_looks_gateway_shaped():
    # Multiple devices share the controller's host value, but none of
    # them have a gateway-shaped model name, so we shouldn't guess.
    records = [
        _unifi_record("192.0.2.1", "192.0.2.50", "U6-Lite", "AP-LivingRoom"),
        _unifi_record("192.0.2.1", "192.0.2.51", "USW Flex", "Switch-Garage"),
    ]

    dot = build_diagram(records, gateway_ip="192.0.2.1")
    source = dot.source

    assert "Network" in source
    assert "(gateway)" not in source


def test_build_diagram_does_not_treat_lone_non_gateway_shaped_unifi_device_as_gateway():
    # A single UniFi device happening to be the only record present (e.g.
    # a partial collection run) still only matches gateway_ip through the
    # shared controller "host" value, not through owning that address
    # itself. A lone host match must not be trusted outright the way it
    # would be for a non-UniFi vendor with a genuine per-device host.
    records = [
        _unifi_record("192.0.2.1", "192.0.2.50", "U6-Lite", "AP-LivingRoom"),
    ]

    dot = build_diagram(records, gateway_ip="192.0.2.1")
    source = dot.source

    assert "Network" in source
    assert "(gateway)" not in source
    assert "AP-LivingRoom" in source


def test_find_gateway_record_returns_none_when_two_candidates_both_look_gateway_shaped():
    # Ambiguous tie: more than one candidate looks gateway-shaped (e.g. two
    # UDM-model records sharing the controller host). Don't guess which
    # one is the real console.
    records = [
        _unifi_record("192.0.2.1", "192.0.2.50", "UDM Pro", "Dream-Machine"),
        _unifi_record("192.0.2.1", "192.0.2.51", "UDM SE", "Dream-Machine-2"),
    ]

    assert _find_gateway_record(records, "192.0.2.1") is None


def test_find_gateway_record_does_not_crash_on_null_interfaces():
    # "interfaces": null is valid JSON and plausible from hand-edited or
    # partially-written output; only "interfaces" being absent gets the
    # empty-list default from record.get(), so an explicit None must be
    # handled too instead of raising when iterated over.
    records = [
        {"vendor": "unifi", "host": "192.0.2.99", "model": "U6-Lite", "interfaces": None},
    ]

    assert _find_gateway_record(records, "198.51.100.1") is None


def test_build_diagram_matches_single_candidate_by_host_for_non_unifi_vendor():
    # Junos/EXOS style records have a real, unique per-device host, so a
    # single match is unambiguous with no model disambiguation needed.
    records = [
        _record("juniper", "10.0.0.1", "ex4300", hostname="core-sw"),
        _record("extreme", "10.0.0.2", "x440", hostname="edge-sw"),
    ]

    dot = build_diagram(records, gateway_ip="10.0.0.1")
    source = dot.source

    assert "core-sw" in source and "(gateway)" in source
    assert "edge-sw" in source
    assert source.count("--") == 1


def test_build_diagram_falls_back_to_generic_hub_when_gateway_not_found():
    dot = build_diagram([_record("juniper", "10.0.0.1", "ex4300")], gateway_ip="10.0.0.99")

    assert "Network" in dot.source
    assert "(gateway)" not in dot.source


def test_build_diagram_handles_empty_records():
    dot = build_diagram([])

    assert "network" in dot.source


def test_default_gateway_ip_parses_macos_route_output():
    fake_result = type("R", (), {"stdout": "   route to: default\n   gateway: 192.0.2.1\n"})()

    with patch("diagram.sys.platform", "darwin"), \
         patch("diagram.subprocess.run", return_value=fake_result):
        assert default_gateway_ip() == "192.0.2.1"


def test_default_gateway_ip_parses_linux_route_output():
    fake_result = type("R", (), {"stdout": "default via 192.0.2.1 dev eth0 proto dhcp\n"})()

    with patch("diagram.sys.platform", "linux"), \
         patch("diagram.subprocess.run", return_value=fake_result):
        assert default_gateway_ip() == "192.0.2.1"


def test_default_gateway_ip_returns_none_when_command_missing():
    with patch("diagram.sys.platform", "darwin"), \
         patch("diagram.subprocess.run", side_effect=FileNotFoundError()):
        assert default_gateway_ip() is None


def test_main_skips_rendering_when_nothing_collected(capsys):
    with patch("diagram.load_all_records", return_value=[]), \
         patch("diagram.build_diagram") as mock_build:
        main()

    mock_build.assert_not_called()
    assert "No collected inventory found" in capsys.readouterr().out


def test_main_renders_when_records_exist(tmp_path):
    records = [_record("juniper", "10.0.0.1", "ex4300", hostname="sw1")]

    with patch("diagram.load_all_records", return_value=records), \
         patch("diagram.default_gateway_ip", return_value=None), \
         patch("diagram.OUTPUT_DIR", str(tmp_path)):
        main()

    assert (tmp_path / "device_diagram.png").exists()
