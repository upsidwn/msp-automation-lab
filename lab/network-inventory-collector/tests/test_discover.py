import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from discover import discover


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
         patch("discover.try_ssh_device_types", return_value=None):
        records, unidentified = discover("10.0.0.0/24")

    assert records == []
    assert len(unidentified) == 1
    assert unidentified[0]["ip"] == "10.0.0.2"


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
         patch("discover.collector_unifi.collect_all", side_effect=RequestsConnectionError()):
        records, unidentified = discover("10.0.0.0/24")

    assert records == []
    assert len(unidentified) == 1


def test_no_open_relevant_ports_is_unidentified():
    candidates = [_candidate("10.0.0.5", [8080])]

    with patch("discover.scan", return_value=candidates), \
         patch("discover.load_credential_pool", return_value=[]):
        records, unidentified = discover("10.0.0.0/24")

    assert records == []
    assert len(unidentified) == 1
