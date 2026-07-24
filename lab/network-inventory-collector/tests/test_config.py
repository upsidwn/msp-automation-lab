import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from config import MissingConfigError, load_juniper_config


def test_load_juniper_config_success(monkeypatch):
    monkeypatch.setenv("NIC_JUNOS_HOST", "10.0.0.1")
    monkeypatch.setenv("NIC_JUNOS_USER", "admin")
    monkeypatch.setenv("NIC_JUNOS_PASS", "secret")

    assert load_juniper_config() == {
        "host": "10.0.0.1",
        "username": "admin",
        "password": "secret",
    }


def test_load_juniper_config_missing_var(monkeypatch):
    monkeypatch.delenv("NIC_JUNOS_HOST", raising=False)
    monkeypatch.delenv("NIC_JUNOS_USER", raising=False)
    monkeypatch.delenv("NIC_JUNOS_PASS", raising=False)

    with pytest.raises(MissingConfigError):
        load_juniper_config()
