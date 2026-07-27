import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import mdns_discovery


class _FakeInfo:
    def __init__(self, service_type, server, addresses):
        self.type = service_type
        self.server = server
        self._addresses = addresses

    def parsed_addresses(self, version=None):
        return self._addresses


def test_merge_by_ip_collapses_multiple_services_on_one_device():
    infos = [
        _FakeInfo("_ipp._tcp.local.", "printer1.local.", ["10.0.0.5"]),
        _FakeInfo("_http._tcp.local.", "printer1.local.", ["10.0.0.5"]),
    ]

    result = mdns_discovery.merge_by_ip(infos)

    assert len(result) == 1
    assert result[0]["ip"] == "10.0.0.5"
    assert result[0]["hostname"] == "printer1.local"
    assert result[0]["services"] == ["_http._tcp.local.", "_ipp._tcp.local."]


def test_merge_by_ip_keeps_separate_devices_apart():
    infos = [
        _FakeInfo("_airplay._tcp.local.", "tv.local.", ["10.0.0.6"]),
        _FakeInfo("_googlecast._tcp.local.", "chromecast.local.", ["10.0.0.7"]),
    ]

    result = mdns_discovery.merge_by_ip(infos)

    assert {c["ip"] for c in result} == {"10.0.0.6", "10.0.0.7"}


def test_merge_by_ip_handles_missing_hostname():
    infos = [_FakeInfo("_workstation._tcp.local.", None, ["10.0.0.8"])]

    result = mdns_discovery.merge_by_ip(infos)

    assert result[0]["hostname"] is None
    assert result[0]["services"] == ["_workstation._tcp.local."]


def test_merge_by_ip_returns_empty_for_no_infos():
    assert mdns_discovery.merge_by_ip([]) == []


def test_merge_by_ip_drops_loopback_address():
    infos = [_FakeInfo("_airplay._tcp.local.", "this-box.local.", ["127.0.0.1", "10.0.0.50"])]

    result = mdns_discovery.merge_by_ip(infos)

    assert len(result) == 1
    assert result[0]["ip"] == "10.0.0.50"


def test_merge_by_ip_strips_control_characters_from_hostname():
    hostile = "evil\x1b[31mname.local."
    infos = [_FakeInfo("_http._tcp.local.", hostile, ["10.0.0.60"])]

    result = mdns_discovery.merge_by_ip(infos)

    assert "\x1b" not in result[0]["hostname"]


def test_merge_by_ip_strips_control_characters_from_service_type():
    hostile_type = "_http\r\n._tcp.local."
    infos = [_FakeInfo(hostile_type, "thing.local.", ["10.0.0.61"])]

    result = mdns_discovery.merge_by_ip(infos)

    assert all("\r" not in s and "\n" not in s for s in result[0]["services"])


def test_listen_returns_empty_when_no_service_types_found():
    with patch("mdns_discovery.Zeroconf") as mock_zc_cls, \
         patch("mdns_discovery.ZeroconfServiceTypes") as mock_types_cls:
        mock_zc = MagicMock()
        mock_zc_cls.return_value = mock_zc
        mock_types_cls.find.return_value = ()

        result = mdns_discovery.listen(duration=1)

    assert result == []
    mock_zc.close.assert_called_once()


def test_listen_browses_found_types_and_returns_collected_info():
    fake_info = _FakeInfo("_http._tcp.local.", "thing.local.", ["10.0.0.9"])

    def fake_browser(zc, types, listener):
        listener.add_service(zc, "_http._tcp.local.", "thing._http._tcp.local.")
        return MagicMock()

    with patch("mdns_discovery.Zeroconf") as mock_zc_cls, \
         patch("mdns_discovery.ZeroconfServiceTypes") as mock_types_cls, \
         patch("mdns_discovery.ServiceBrowser", side_effect=fake_browser), \
         patch("mdns_discovery.time.sleep"):
        mock_zc = MagicMock()
        mock_zc.get_service_info.return_value = fake_info
        mock_zc_cls.return_value = mock_zc
        mock_types_cls.find.return_value = ("_http._tcp.local.",)

        result = mdns_discovery.listen(duration=1)

    assert result == [fake_info]
    mock_zc.close.assert_called_once()


def test_listen_calls_on_update_as_services_resolve_live():
    fake_info = _FakeInfo("_http._tcp.local.", "thing.local.", ["10.0.0.20"])
    updates = []

    def fake_browser(zc, types, listener):
        listener.add_service(zc, "_http._tcp.local.", "thing._http._tcp.local.")
        return MagicMock()

    with patch("mdns_discovery.Zeroconf") as mock_zc_cls, \
         patch("mdns_discovery.ZeroconfServiceTypes") as mock_types_cls, \
         patch("mdns_discovery.ServiceBrowser", side_effect=fake_browser), \
         patch("mdns_discovery.time.sleep"):
        mock_zc = MagicMock()
        mock_zc.get_service_info.return_value = fake_info
        mock_zc_cls.return_value = mock_zc
        mock_types_cls.find.return_value = ("_http._tcp.local.",)

        mdns_discovery.listen(duration=1, on_update=updates.append)

    assert len(updates) == 1
    assert updates[0]["ip"] == "10.0.0.20"
    assert updates[0]["hostname"] == "thing.local"


def test_incremental_merge_calls_on_update_per_service_with_running_state():
    updates = []
    merger = mdns_discovery._IncrementalMerge(on_update=updates.append)

    merger.add(_FakeInfo("_ipp._tcp.local.", "printer1.local.", ["10.0.0.21"]))
    merger.add(_FakeInfo("_http._tcp.local.", "printer1.local.", ["10.0.0.21"]))

    assert len(updates) == 2
    assert updates[0]["services"] == ["_ipp._tcp.local."]
    assert updates[1]["services"] == ["_http._tcp.local.", "_ipp._tcp.local."]


def test_incremental_merge_result_matches_merge_by_ip():
    infos = [
        _FakeInfo("_ipp._tcp.local.", "printer1.local.", ["10.0.0.22"]),
        _FakeInfo("_airplay._tcp.local.", "tv.local.", ["10.0.0.23"]),
    ]

    merger = mdns_discovery._IncrementalMerge()
    for info in infos:
        merger.add(info)

    assert merger.result() == mdns_discovery.merge_by_ip(infos)


def test_listen_closes_zeroconf_even_if_browsing_raises():
    with patch("mdns_discovery.Zeroconf") as mock_zc_cls, \
         patch("mdns_discovery.ZeroconfServiceTypes") as mock_types_cls:
        mock_zc = MagicMock()
        mock_zc_cls.return_value = mock_zc
        mock_types_cls.find.side_effect = RuntimeError("network unreachable")

        try:
            mdns_discovery.listen(duration=1)
        except RuntimeError:
            pass

    mock_zc.close.assert_called_once()


def test_listen_returns_empty_for_non_positive_duration():
    with patch("mdns_discovery.Zeroconf") as mock_zc_cls:
        result = mdns_discovery.listen(duration=0)

    assert result == []
    mock_zc_cls.assert_not_called()


def test_collecting_listener_skips_a_malformed_record_without_raising():
    listener = mdns_discovery._CollectingListener()
    zc = MagicMock()
    zc.get_service_info.side_effect = Exception("bad type in name")

    listener.add_service(zc, "_http._tcp.local.", "broken._http._tcp.local.")

    assert listener.seen == {}


def test_collecting_listener_keeps_good_records_after_a_bad_one():
    listener = mdns_discovery._CollectingListener()
    zc = MagicMock()
    good_info = _FakeInfo("_http._tcp.local.", "thing.local.", ["10.0.0.62"])
    zc.get_service_info.side_effect = [Exception("bad record"), good_info]

    listener.add_service(zc, "_http._tcp.local.", "broken._http._tcp.local.")
    listener.add_service(zc, "_http._tcp.local.", "thing._http._tcp.local.")

    assert list(listener.seen.values()) == [good_info]
