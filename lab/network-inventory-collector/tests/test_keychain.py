import json
import os
import sys
from unittest.mock import patch

import keyring.errors

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from keychain import SERVICE, delete_credential, load_credential, save_credential


def test_save_credential_stores_json_blob():
    with patch("keychain.keyring.set_password") as mock_set:
        save_credential("10.0.0.1", {"username": "admin", "password": "pw"})

    mock_set.assert_called_once_with(SERVICE, "10.0.0.1", json.dumps({"username": "admin", "password": "pw"}))


def test_load_credential_returns_saved_fields():
    with patch("keychain.keyring.get_password", return_value=json.dumps({"username": "admin", "password": "pw"})):
        result = load_credential("10.0.0.1")

    assert result == {"username": "admin", "password": "pw"}


def test_load_credential_returns_none_when_nothing_saved():
    with patch("keychain.keyring.get_password", return_value=None):
        assert load_credential("10.0.0.1") is None


def test_delete_credential_removes_entry():
    with patch("keychain.keyring.delete_password") as mock_delete:
        delete_credential("10.0.0.1")

    mock_delete.assert_called_once_with(SERVICE, "10.0.0.1")


def test_delete_credential_ignores_missing_entry():
    with patch("keychain.keyring.delete_password", side_effect=keyring.errors.PasswordDeleteError()):
        delete_credential("10.0.0.1")  # should not raise
