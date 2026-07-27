import logging
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import auth  # noqa: F401, importing this module is the thing under test here
from auth import connect_with_pool, prompt_and_retry_ssh, try_ssh_device_types
from netmiko import NetmikoAuthenticationException, NetmikoTimeoutException


def test_importing_auth_silences_paramikos_own_error_logging():
    # Confirmed live: a host with port 22 open but not actually running
    # SSH makes paramiko log its own raw traceback on top of the
    # exception this module already catches and reports cleanly,
    # flooding the terminal during a real discover.py scan.
    assert logging.getLogger("paramiko").getEffectiveLevel() >= logging.CRITICAL


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


def test_prompt_and_retry_ssh_returns_none_when_declined():
    pool = []

    with patch("builtins.input", return_value="n"), \
         patch("auth.ConnectHandler", side_effect=AssertionError("should never connect")):
        result = prompt_and_retry_ssh("10.0.0.1", pool, ["juniper_junos"])

    assert result is None
    assert pool == []


def test_prompt_and_retry_ssh_finds_vendor_and_appends_to_pool():
    pool = []
    fake_conn = MagicMock()

    def fake_connect(device_type, host, username, password):
        if device_type != "extreme_exos":
            raise NetmikoAuthenticationException()
        return fake_conn

    with patch("auth.ConnectHandler", side_effect=fake_connect), \
         patch("builtins.input", side_effect=["y", "admin"]), \
         patch("auth.getpass.getpass", return_value="pw"):
        result = prompt_and_retry_ssh("10.0.0.1", pool, ["juniper_junos", "extreme_exos"])

    assert result == ("extreme_exos", fake_conn)
    assert pool == [{"username": "admin", "password": "pw"}]


def test_prompt_and_retry_ssh_reprompts_after_a_failed_attempt():
    pool = []
    fake_conn = MagicMock()
    attempts = {"count": 0}

    def fake_connect(device_type, host, username, password):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise NetmikoAuthenticationException()
        return fake_conn

    with patch("auth.ConnectHandler", side_effect=fake_connect), \
         patch("builtins.input", side_effect=["y", "baduser", "y", "gooduser"]), \
         patch("auth.getpass.getpass", side_effect=["badpass", "goodpass"]):
        result = prompt_and_retry_ssh("10.0.0.1", pool, ["juniper_junos"])

    assert result == ("juniper_junos", fake_conn)
    assert attempts["count"] == 2
    assert pool == [{"username": "gooduser", "password": "goodpass"}]


def test_prompt_and_retry_ssh_gives_up_when_retry_declined():
    pool = []

    def fake_connect(device_type, host, username, password):
        raise NetmikoAuthenticationException()

    with patch("auth.ConnectHandler", side_effect=fake_connect), \
         patch("builtins.input", side_effect=["y", "baduser", "n"]), \
         patch("auth.getpass.getpass", return_value="badpass"):
        result = prompt_and_retry_ssh("10.0.0.1", pool, ["juniper_junos"])

    assert result is None
    assert pool == []
