import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from discover import discover, main
from subnet_detect import SubnetDetectionError


def _candidate(ip, ports):
    return {"ip": ip, "mac": None, "ports": [{"port": p, "protocol": "tcp", "service": None, "product": None, "version": None} for p in ports]}


@pytest.fixture(autouse=True)
def no_env_creds(monkeypatch):
    # Keep tests independent of whatever is (or isn't) in a real .env.
    for var in ["NIC_UNIFI_HOST", "NIC_UNIFI_API_KEY"]:
        monkeypatch.delenv(var, raising=False)


def test_ssh_candidate_dispatches_to_matching_vendor():
    candidates = [_candidate("10.0.0.1", [22])]
    fake_record = {"host": "10.0.0.1", "vendor": "extreme", "model": "lab-switch-2"}

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[{"username": "a", "password": "b"}]), \
         patch("discover.try_ssh_device_types", return_value=("extreme_exos", MagicMock())), \
         patch("discover.SSH_COLLECTORS", {"extreme_exos": lambda conn, host: fake_record}):
        records, unidentified = discover("10.0.0.0/24")

    assert records == [fake_record]
    assert unidentified == []


def test_unmatched_ssh_candidate_is_unidentified():
    candidates = [_candidate("10.0.0.2", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.arp_lookup.get_mac", return_value=None), \
         patch("discover.oui_lookup.get_vendor", return_value=None):
        records, unidentified = discover("10.0.0.0/24")

    assert records == []
    assert len(unidentified) == 1
    assert unidentified[0]["ip"] == "10.0.0.2"


def test_unidentified_candidate_gets_enriched_with_mac_and_vendor():
    candidates = [_candidate("10.0.0.6", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.arp_lookup.get_mac", return_value="aa:bb:cc:dd:ee:ff"), \
         patch("discover.oui_lookup.get_vendor", return_value="Some Vendor Inc"):
        _records, unidentified = discover("10.0.0.0/24")

    assert unidentified[0]["mac"] == "aa:bb:cc:dd:ee:ff"
    assert unidentified[0]["mac_vendor"] == "Some Vendor Inc"


def test_unidentified_candidate_prefers_nmaps_own_mac_over_arp_lookup():
    candidates = [_candidate("10.0.0.7", [22])]
    candidates[0]["mac"] = "11:22:33:44:55:66"

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.arp_lookup.get_mac") as mock_arp, \
         patch("discover.oui_lookup.get_vendor", return_value=None):
        discover("10.0.0.0/24")

    mock_arp.assert_not_called()


def test_unifi_candidate_dispatches_when_configured():
    candidates = [_candidate("10.0.0.3", [443])]
    fake_records = [{"host": "10.0.0.3", "vendor": "unifi", "model": "lab-ap-1"}]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.load_unifi_config", return_value={"host": "10.0.0.3", "api_key": "fake-key"}), \
         patch("discover.collector_unifi.collect_all", return_value=fake_records):
        records, unidentified = discover("10.0.0.0/24")

    assert records == fake_records
    assert unidentified == []


def test_unifi_candidate_falls_back_to_unidentified_on_request_error():
    candidates = [_candidate("10.0.0.4", [443])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.load_unifi_config", return_value={"host": "10.0.0.4", "api_key": "fake-key"}), \
         patch("discover.collector_unifi.collect_all", side_effect=RequestsConnectionError()), \
         patch("discover.arp_lookup.get_mac", return_value=None), \
         patch("discover.oui_lookup.get_vendor", return_value=None):
        records, unidentified = discover("10.0.0.0/24")

    assert records == []
    assert len(unidentified) == 1


def test_auth_failure_prompt_not_used_by_default():
    candidates = [_candidate("10.0.0.9", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.prompt_and_retry_ssh") as mock_prompt, \
         patch("discover.arp_lookup.get_mac", return_value=None), \
         patch("discover.oui_lookup.get_vendor", return_value=None):
        records, unidentified = discover("10.0.0.0/24")

    mock_prompt.assert_not_called()
    assert records == []
    assert len(unidentified) == 1


def test_auth_failure_falls_back_to_interactive_prompt_when_enabled():
    candidates = [_candidate("10.0.0.8", [22])]
    fake_record = {"host": "10.0.0.8", "vendor": "juniper", "model": "lab-switch-3"}

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.prompt_and_retry_ssh", return_value=("juniper_junos", MagicMock())), \
         patch("discover.SSH_COLLECTORS", {"juniper_junos": lambda conn, host: fake_record}):
        records, unidentified = discover("10.0.0.0/24", prompt_on_auth_failure=True)

    assert records == [fake_record]
    assert unidentified == []


def test_auth_failure_prompt_declined_falls_back_to_unidentified():
    candidates = [_candidate("10.0.0.10", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.prompt_and_retry_ssh", return_value=None), \
         patch("discover.arp_lookup.get_mac", return_value=None), \
         patch("discover.oui_lookup.get_vendor", return_value=None):
        records, unidentified = discover("10.0.0.0/24", prompt_on_auth_failure=True)

    assert records == []
    assert len(unidentified) == 1


def test_main_auto_detects_cidr_when_none_given():
    with patch("sys.argv", ["discover.py"]), \
         patch("discover.detect_local_cidr", return_value="10.0.0.0/24"), \
         patch("discover.discover", return_value=([], [])) as mock_discover, \
         patch("builtins.open"), \
         patch("json.dump"):
        main()

    assert mock_discover.call_args.args[0] == "10.0.0.0/24"


def test_main_skips_detection_when_cidr_given_explicitly():
    with patch("sys.argv", ["discover.py", "10.1.2.0/24"]), \
         patch("discover.detect_local_cidr") as mock_detect, \
         patch("discover.discover", return_value=([], [])) as mock_discover, \
         patch("builtins.open"), \
         patch("json.dump"):
        main()

    mock_detect.assert_not_called()
    assert mock_discover.call_args.args[0] == "10.1.2.0/24"


def test_main_gives_up_cleanly_when_detection_fails():
    with patch("sys.argv", ["discover.py"]), \
         patch("discover.detect_local_cidr", side_effect=SubnetDetectionError("no route")), \
         patch("discover.discover") as mock_discover:
        main()

    mock_discover.assert_not_called()


def test_main_rejects_an_invalid_explicit_cidr():
    # Confirmed live: a bare "24" (not a real CIDR) got passed straight
    # through and nmap/arp-scan both misparsed it leniently instead of
    # erroring, so the whole scan silently ran against nothing.
    with patch("sys.argv", ["discover.py", "24"]), \
         patch("discover.discover") as mock_discover:
        main()

    mock_discover.assert_not_called()


def test_main_accepts_a_plain_ip_without_a_prefix():
    with patch("sys.argv", ["discover.py", "10.0.0.5"]), \
         patch("discover.discover", return_value=([], [])) as mock_discover, \
         patch("builtins.open"), \
         patch("json.dump"):
        main()

    assert mock_discover.call_args.args[0] == "10.0.0.5"


def test_main_reports_the_actual_missing_command_not_always_nmap():
    # Confirmed live: this handler used to unconditionally blame nmap
    # for any FileNotFoundError, but arp_lookup.py shells out to a
    # different command ("arp") that can go missing independently, a
    # minimal container without net-tools hit this exact case.
    missing_command_error = FileNotFoundError(2, "No such file or directory")
    missing_command_error.filename = "arp"

    with patch("sys.argv", ["discover.py", "10.0.0.0/24"]), \
         patch("discover.discover", side_effect=missing_command_error), \
         patch("builtins.print") as mock_print:
        main()

    printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
    assert "arp" in printed
    assert "nmap not found" not in printed


def test_no_open_relevant_ports_is_unidentified():
    candidates = [_candidate("10.0.0.5", [8080])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.arp_lookup.get_mac", return_value=None), \
         patch("discover.oui_lookup.get_vendor", return_value=None):
        records, unidentified = discover("10.0.0.0/24")

    assert records == []
    assert len(unidentified) == 1


def test_mdns_disabled_by_default_does_not_listen():
    candidates = [_candidate("10.0.0.20", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.arp_lookup.get_mac", return_value=None), \
         patch("discover.oui_lookup.get_vendor", return_value=None), \
         patch("discover.mdns_discovery.listen") as mock_listen:
        discover("10.0.0.0/24")

    mock_listen.assert_not_called()


def test_mdns_candidate_at_new_ip_becomes_unidentified():
    with patch("discover.scan", return_value=[]), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch(
             "discover._mdns_candidates",
             return_value=([{"ip": "10.0.0.30", "hostname": "speaker", "services": ["_airplay._tcp.local."]}], set()),
         ), \
         patch("discover.arp_lookup.get_mac", return_value="aa:bb:cc:00:11:22"), \
         patch("discover.oui_lookup.get_vendor", return_value="Some Vendor"):
        records, unidentified = discover("10.0.0.0/24", mdns_seconds=5)

    assert records == []
    assert len(unidentified) == 1
    entry = unidentified[0]
    assert entry["ip"] == "10.0.0.30"
    assert entry["hostname"] == "speaker"
    assert entry["services"] == ["_airplay._tcp.local."]
    assert entry["mac"] == "aa:bb:cc:00:11:22"
    assert entry["mac_vendor"] == "Some Vendor"


def test_mdns_candidate_at_already_identified_ip_is_skipped():
    fake_record = {"host": "10.0.0.31", "vendor": "juniper", "model": "lab-switch-1"}
    candidates = [_candidate("10.0.0.31", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[{"username": "a", "password": "b"}]), \
         patch("discover.try_ssh_device_types", return_value=("juniper_junos", MagicMock())), \
         patch("discover.SSH_COLLECTORS", {"juniper_junos": lambda conn, host: fake_record}), \
         patch(
             "discover._mdns_candidates",
             return_value=([{"ip": "10.0.0.31", "hostname": "switch1", "services": ["_ssh._tcp.local."]}], set()),
         ):
        records, unidentified = discover("10.0.0.0/24", mdns_seconds=5)

    assert records == [fake_record]
    assert unidentified == []


def test_mdns_candidate_merges_into_existing_unidentified_entry():
    candidates = [_candidate("10.0.0.32", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.arp_lookup.get_mac", return_value="11:22:33:44:55:66"), \
         patch("discover.oui_lookup.get_vendor", return_value="Nmap-Seen Vendor"), \
         patch(
             "discover._mdns_candidates",
             return_value=([{"ip": "10.0.0.32", "hostname": "mystery-box", "services": ["_http._tcp.local."]}], set()),
         ):
        records, unidentified = discover("10.0.0.0/24", mdns_seconds=5)

    assert records == []
    assert len(unidentified) == 1
    entry = unidentified[0]
    assert entry["mac"] == "11:22:33:44:55:66"
    assert entry["mac_vendor"] == "Nmap-Seen Vendor"
    assert entry["hostname"] == "mystery-box"
    assert entry["services"] == ["_http._tcp.local."]


def test_nmap_only_unidentified_entry_has_hostname_and_services_keys():
    candidates = [_candidate("10.0.0.33", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.arp_lookup.get_mac", return_value=None), \
         patch("discover.oui_lookup.get_vendor", return_value=None):
        _records, unidentified = discover("10.0.0.0/24")

    assert unidentified[0]["hostname"] is None
    assert unidentified[0]["services"] == []


def test_mdns_failure_does_not_lose_already_collected_results():
    fake_record = {"host": "10.0.0.34", "vendor": "juniper", "model": "lab-switch-1"}
    candidates = [_candidate("10.0.0.34", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[{"username": "a", "password": "b"}]), \
         patch("discover.try_ssh_device_types", return_value=("juniper_junos", MagicMock())), \
         patch("discover.SSH_COLLECTORS", {"juniper_junos": lambda conn, host: fake_record}), \
         patch("discover._mdns_candidates", side_effect=RuntimeError("mdns blew up")):
        records, unidentified = discover("10.0.0.0/24", mdns_seconds=5)

    assert records == [fake_record]
    assert unidentified == []


def test_arp_sweep_disabled_by_default_does_not_scan():
    candidates = [_candidate("10.0.0.40", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.arp_lookup.get_mac", return_value=None), \
         patch("discover.oui_lookup.get_vendor", return_value=None), \
         patch("discover.arp_scan.scan") as mock_arp_scan:
        discover("10.0.0.0/24")

    mock_arp_scan.assert_not_called()


def test_arp_candidate_at_new_ip_becomes_unidentified():
    with patch("discover.scan", return_value=[]), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch(
             "discover.arp_scan.scan",
             return_value=[{"ip": "10.0.0.41", "mac": "aa:bb:cc:00:11:41", "vendor": "Some Vendor"}],
         ):
        records, unidentified = discover("10.0.0.0/24", arp_sweep=True)

    assert records == []
    assert len(unidentified) == 1
    entry = unidentified[0]
    assert entry["ip"] == "10.0.0.41"
    assert entry["mac"] == "aa:bb:cc:00:11:41"
    assert entry["mac_vendor"] == "Some Vendor"
    assert entry["hostname"] is None
    assert entry["services"] == []


def test_arp_candidate_at_already_identified_ip_is_skipped():
    fake_record = {"host": "10.0.0.42", "vendor": "juniper", "model": "lab-switch-1"}
    candidates = [_candidate("10.0.0.42", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[{"username": "a", "password": "b"}]), \
         patch("discover.try_ssh_device_types", return_value=("juniper_junos", MagicMock())), \
         patch("discover.SSH_COLLECTORS", {"juniper_junos": lambda conn, host: fake_record}), \
         patch(
             "discover.arp_scan.scan",
             return_value=[{"ip": "10.0.0.42", "mac": "11:22:33:44:55:66", "vendor": "Some Vendor"}],
         ):
        records, unidentified = discover("10.0.0.0/24", arp_sweep=True)

    assert records == [fake_record]
    assert unidentified == []


def test_arp_candidate_fills_in_missing_mac_on_existing_unidentified_entry():
    candidates = [_candidate("10.0.0.43", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.arp_lookup.get_mac", return_value=None), \
         patch("discover.oui_lookup.get_vendor", return_value=None), \
         patch(
             "discover.arp_scan.scan",
             return_value=[{"ip": "10.0.0.43", "mac": "aa:aa:aa:aa:aa:aa", "vendor": "ARP Vendor"}],
         ):
        records, unidentified = discover("10.0.0.0/24", arp_sweep=True)

    assert records == []
    assert len(unidentified) == 1
    entry = unidentified[0]
    assert entry["mac"] == "aa:aa:aa:aa:aa:aa"
    assert entry["mac_vendor"] == "ARP Vendor"


def test_arp_sweep_failure_does_not_lose_already_collected_results():
    fake_record = {"host": "10.0.0.44", "vendor": "juniper", "model": "lab-switch-1"}
    candidates = [_candidate("10.0.0.44", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[{"username": "a", "password": "b"}]), \
         patch("discover.try_ssh_device_types", return_value=("juniper_junos", MagicMock())), \
         patch("discover.SSH_COLLECTORS", {"juniper_junos": lambda conn, host: fake_record}), \
         patch("discover.arp_scan.scan", side_effect=RuntimeError("arp-scan blew up")):
        records, unidentified = discover("10.0.0.0/24", arp_sweep=True)

    assert records == [fake_record]
    assert unidentified == []


def test_arp_sweep_declined_sudo_returns_no_candidates_without_error():
    candidates = [_candidate("10.0.0.45", [22])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.arp_lookup.get_mac", return_value=None), \
         patch("discover.oui_lookup.get_vendor", return_value=None), \
         patch("discover.arp_scan.scan", return_value=None):
        records, unidentified = discover("10.0.0.0/24", arp_sweep=True)

    assert records == []
    assert len(unidentified) == 1
    assert unidentified[0]["ip"] == "10.0.0.45"


def test_identified_ssh_device_updates_the_live_table():
    fake_record = {"host": "10.0.0.50", "vendor": "juniper", "model": "lab-switch-1"}
    candidates = [_candidate("10.0.0.50", [22])]
    fake_table = MagicMock()

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[{"username": "a", "password": "b"}]), \
         patch("discover.try_ssh_device_types", return_value=("juniper_junos", MagicMock())), \
         patch("discover.SSH_COLLECTORS", {"juniper_junos": lambda conn, host: fake_record}):
        discover("10.0.0.0/24", table=fake_table)

    scanning_call = [c for c in fake_table.upsert.call_args_list if c.args == ("10.0.0.50",) and c.kwargs.get("status") == "scanning..."]
    assert scanning_call

    identified_call = [
        c for c in fake_table.upsert.call_args_list if c.args == ("10.0.0.50",) and c.kwargs.get("vendor")
    ]
    assert identified_call
    assert identified_call[0].kwargs["vendor"] == "juniper"
    assert identified_call[0].kwargs["model"] == "lab-switch-1"
    assert identified_call[0].kwargs["status"] == ""


def test_unidentified_device_updates_the_live_table_with_status():
    candidates = [_candidate("10.0.0.51", [22])]
    fake_table = MagicMock()

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.try_ssh_device_types", return_value=None), \
         patch("discover.arp_lookup.get_mac", return_value=None), \
         patch("discover.oui_lookup.get_vendor", return_value=None):
        discover("10.0.0.0/24", table=fake_table)

    status_call = [
        c for c in fake_table.upsert.call_args_list if c.args == ("10.0.0.51",) and "unidentified" in c.kwargs.get("status", "")
    ]
    assert status_call


def test_mdns_candidate_updates_the_live_table():
    fake_table = MagicMock()

    with patch("discover.scan", return_value=[]), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch(
             "discover._mdns_candidates",
             return_value=([{"ip": "10.0.0.52", "hostname": "speaker", "services": ["_airplay._tcp.local."]}], set()),
         ):
        discover("10.0.0.0/24", mdns_seconds=5, table=fake_table)

    mdns_call = [c for c in fake_table.upsert.call_args_list if c.args == ("10.0.0.52",) and c.kwargs.get("hostname")]
    assert mdns_call
    assert mdns_call[0].kwargs["hostname"] == "speaker"


def test_arp_candidate_updates_the_live_table():
    fake_table = MagicMock()

    with patch("discover.scan", return_value=[]), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch(
             "discover.arp_scan.scan",
             return_value=[{"ip": "10.0.0.53", "mac": "aa:bb:cc:00:11:53", "vendor": "Some Vendor"}],
         ):
        discover("10.0.0.0/24", arp_sweep=True, table=fake_table)

    arp_call = [c for c in fake_table.upsert.call_args_list if c.args == ("10.0.0.53",) and c.kwargs.get("mac")]
    assert arp_call
    assert arp_call[0].kwargs["mac"] == "aa:bb:cc:00:11:53"
    assert arp_call[0].kwargs["mac_vendor"] == "Some Vendor"


def test_mdns_candidate_outside_requested_cidr_is_dropped():
    # Confirmed live: mDNS is a passive listen with no concept of subnet
    # boundaries, so on a flat network bigger than the requested CIDR it
    # happily reports devices way outside it.
    in_cidr = {"ip": "10.0.0.60", "hostname": "in-range", "services": ["_http._tcp.local."]}
    out_of_cidr = {"ip": "10.0.9.60", "hostname": "out-of-range", "services": ["_http._tcp.local."]}

    with patch("discover.scan", return_value=[]), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.mdns_discovery.listen", return_value=[]), \
         patch("discover.mdns_discovery.merge_by_ip", return_value=[in_cidr, out_of_cidr]):
        _records, unidentified = discover("10.0.0.0/24", mdns_seconds=5)

    ips = {u["ip"] for u in unidentified}
    assert ips == {"10.0.0.60"}


def test_arp_candidate_outside_requested_cidr_is_dropped():
    in_cidr = {"ip": "10.0.0.61", "mac": "aa:bb:cc:00:11:61", "vendor": "In Range Vendor"}
    out_of_cidr = {"ip": "10.0.9.61", "mac": "aa:bb:cc:00:11:62", "vendor": "Out Of Range Vendor"}

    with patch("discover.scan", return_value=[]), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.arp_scan.scan", return_value=[in_cidr, out_of_cidr]):
        _records, unidentified = discover("10.0.0.0/24", arp_sweep=True)

    ips = {u["ip"] for u in unidentified}
    assert ips == {"10.0.0.61"}


def test_mdns_out_of_cidr_candidate_never_reaches_the_live_table():
    in_cidr = {"ip": "10.0.0.62", "hostname": "in-range", "services": []}
    out_of_cidr = {"ip": "10.0.9.62", "hostname": "out-of-range", "services": []}
    fake_table = MagicMock()

    with patch("discover.scan", return_value=[]), \
         patch("discover.load_credential_pool", return_value=[]), \
         patch("discover.mdns_discovery.listen", return_value=[]), \
         patch("discover.mdns_discovery.merge_by_ip", return_value=[in_cidr, out_of_cidr]):
        discover("10.0.0.0/24", mdns_seconds=5, table=fake_table)

    upserted_ips = {c.args[0] for c in fake_table.upsert.call_args_list}
    assert "10.0.9.62" not in upserted_ips
    assert "10.0.0.62" in upserted_ips
