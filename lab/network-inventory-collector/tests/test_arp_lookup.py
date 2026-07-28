import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from arp_lookup import get_mac


def _fake_result(stdout):
    result = MagicMock()
    result.stdout = stdout
    return result


def test_get_mac_parses_and_normalizes_unpadded_octet():
    # Real macOS `arp` output doesn't zero-pad single-digit hex octets.
    stdout = "? (192.0.2.10) at aa:bb:cc:dd:ee:0 on en0 ifscope [ethernet]\n"

    with patch("arp_lookup.subprocess.run", return_value=_fake_result(stdout)):
        assert get_mac("192.0.2.10") == "aa:bb:cc:dd:ee:00"


def test_get_mac_parses_fully_padded_mac():
    stdout = "? (192.0.2.1) at aa:bb:cc:dd:ee:ff on en0 ifscope [ethernet]\n"

    with patch("arp_lookup.subprocess.run", return_value=_fake_result(stdout)):
        assert get_mac("192.0.2.1") == "aa:bb:cc:dd:ee:ff"


def test_get_mac_returns_none_for_incomplete_entry():
    stdout = "? (192.0.2.5) at (incomplete) on en0 ifscope [ethernet]\n"

    with patch("arp_lookup.subprocess.run", return_value=_fake_result(stdout)):
        assert get_mac("192.0.2.5") is None


def test_get_mac_returns_none_for_empty_output():
    with patch("arp_lookup.subprocess.run", return_value=_fake_result("")):
        assert get_mac("192.0.2.99") is None


def test_get_mac_returns_none_when_arp_command_is_missing():
    # Confirmed live: a minimal container image without net-tools raised
    # FileNotFoundError here uncaught, crashing the whole scan instead
    # of just leaving this one candidate's MAC unknown.
    with patch("arp_lookup.subprocess.run", side_effect=FileNotFoundError()):
        assert get_mac("192.0.2.42") is None
