# Thin wrapper around the OS keychain (via the keyring package) for
# saving credentials across runs, opt-in only. See docs/NOTES.md: use
# an OS keychain if persistence is ever needed, not a growing .env.
# Stores an arbitrary field dict per key (a host), not just a single
# password, so it works for both username/password and API-key creds.

import json

import keyring

SERVICE = "msp-automation-lab-network-inventory-collector"


def save_credential(key, fields):
    keyring.set_password(SERVICE, key, json.dumps(fields))


def load_credential(key):
    raw = keyring.get_password(SERVICE, key)
    return json.loads(raw) if raw else None


def delete_credential(key):
    try:
        keyring.delete_password(SERVICE, key)
    except keyring.errors.PasswordDeleteError:
        pass
