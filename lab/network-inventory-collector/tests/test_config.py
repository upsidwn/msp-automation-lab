import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from config import MissingConfigError, load_credential_pool, load_juniper_host


def test_load_juniper_host_success(monkeypatch):
    monkeypatch.setenv("NIC_JUNOS_HOST", "10.0.0.1")

    assert load_juniper_host() == "10.0.0.1"


def test_load_juniper_host_missing(monkeypatch):
    monkeypatch.delenv("NIC_JUNOS_HOST", raising=False)

    with pytest.raises(MissingConfigError):
        load_juniper_host()


def test_load_credential_pool_empty(monkeypatch):
    monkeypatch.delenv("NIC_CRED_1_USER", raising=False)
    monkeypatch.delenv("NIC_CRED_1_PASS", raising=False)

    assert load_credential_pool() == []


def test_load_credential_pool_multiple(monkeypatch):
    monkeypatch.setenv("NIC_CRED_1_USER", "admin")
    monkeypatch.setenv("NIC_CRED_1_PASS", "pw1")
    monkeypatch.setenv("NIC_CRED_2_USER", "root")
    monkeypatch.setenv("NIC_CRED_2_PASS", "pw2")
    monkeypatch.delenv("NIC_CRED_3_USER", raising=False)
    monkeypatch.delenv("NIC_CRED_3_PASS", raising=False)

    assert load_credential_pool() == [
        {"username": "admin", "password": "pw1"},
        {"username": "root", "password": "pw2"},
    ]


def test_load_credential_pool_stops_at_first_gap(monkeypatch):
    monkeypatch.setenv("NIC_CRED_1_USER", "admin")
    monkeypatch.setenv("NIC_CRED_1_PASS", "pw1")
    monkeypatch.delenv("NIC_CRED_2_USER", raising=False)
    monkeypatch.delenv("NIC_CRED_2_PASS", raising=False)
    monkeypatch.setenv("NIC_CRED_3_USER", "shouldnotappear")
    monkeypatch.setenv("NIC_CRED_3_PASS", "shouldnotappear")

    assert load_credential_pool() == [{"username": "admin", "password": "pw1"}]
