import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from netmiko import NetmikoAuthenticationException

from auth import connect_with_pool


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
