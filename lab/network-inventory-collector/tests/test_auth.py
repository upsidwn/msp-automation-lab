import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from netmiko import NetmikoAuthenticationException, NetmikoTimeoutException

from auth import connect_with_pool, try_ssh_device_types


def test_uses_first_working_credential_in_pool():
    pool = [
        {"username": "a", "password": "wrong"},
        {"username": "b", "password": "right"},
    ]
    fake_conn = MagicMock()

    def fake_connect(device_type, host, username, password):
        if password != "right":
            raise NetmikoAuthenticationException()
        return fake_conn

    with patch("auth.ConnectHandler", side_effect=fake_connect):
        conn = connect_with_pool("juniper_junos", "10.0.0.1", pool)

    assert conn is fake_conn
    assert pool == [
        {"username": "a", "password": "wrong"},
        {"username": "b", "password": "right"},
    ]


def test_prompts_and_appends_to_pool_when_none_work():
    pool = [{"username": "a", "password": "wrong"}]
    fake_conn = MagicMock()

    def fake_connect(device_type, host, username, password):
        if username == "newuser" and password == "newpass":
            return fake_conn
        raise NetmikoAuthenticationException()

    with patch("auth.ConnectHandler", side_effect=fake_connect), \
         patch("builtins.input", return_value="newuser"), \
         patch("auth.getpass.getpass", return_value="newpass"):
        conn = connect_with_pool("juniper_junos", "10.0.0.1", pool)

    assert conn is fake_conn
    assert pool[-1] == {"username": "newuser", "password": "newpass"}


def test_reprompts_after_a_failed_interactive_attempt():
    pool = []
    fake_conn = MagicMock()
    attempts = {"count": 0}

    def fake_connect(device_type, host, username, password):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise NetmikoAuthenticationException()
        return fake_conn

    with patch("auth.ConnectHandler", side_effect=fake_connect), \
         patch("builtins.input", side_effect=["baduser", "gooduser"]), \
         patch("auth.getpass.getpass", side_effect=["badpass", "goodpass"]):
        conn = connect_with_pool("juniper_junos", "10.0.0.1", pool)

    assert conn is fake_conn
    assert attempts["count"] == 2
    assert pool == [{"username": "gooduser", "password": "goodpass"}]


def test_try_ssh_device_types_finds_matching_vendor():
    pool = [{"username": "admin", "password": "pw"}]
    fake_conn = MagicMock()

    def fake_connect(device_type, host, username, password):
        if device_type != "extreme_exos":
            raise NetmikoTimeoutException("wrong device_type, prompt mismatch")
        return fake_conn

    with patch("auth.ConnectHandler", side_effect=fake_connect):
        result = try_ssh_device_types("10.0.0.1", pool, ["juniper_junos", "extreme_exos"])

    assert result == ("extreme_exos", fake_conn)


def test_try_ssh_device_types_never_prompts_when_nothing_matches():
    pool = [{"username": "admin", "password": "pw"}]

    def fake_connect(device_type, host, username, password):
        raise NetmikoAuthenticationException()

    with patch("auth.ConnectHandler", side_effect=fake_connect), \
         patch("builtins.input", side_effect=AssertionError("should never prompt")):
        result = try_ssh_device_types("10.0.0.1", pool, ["juniper_junos", "extreme_exos"])

    assert result is None


def test_try_ssh_device_types_empty_pool_returns_none():
    result = try_ssh_device_types("10.0.0.1", [], ["juniper_junos", "extreme_exos"])

    assert result is None
