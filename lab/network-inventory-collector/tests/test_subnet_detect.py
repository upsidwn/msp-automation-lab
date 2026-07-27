import os
import socket
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from subnet_detect import (
    SubnetDetectionError,
    detect_local_cidr,
    detect_local_interface,
)


def _fake_addr(family, address, netmask):
    return SimpleNamespace(family=family, address=address, netmask=netmask)


def test_detects_cidr_for_matching_interface():
    fake_sock = MagicMock()
    fake_sock.getsockname.return_value = ("192.168.1.42", 0)
    fake_sock.__enter__.return_value = fake_sock

    fake_if_addrs = {
        "lo0": [_fake_addr(socket.AF_INET, "127.0.0.1", "255.0.0.0")],
        "en0": [_fake_addr(socket.AF_INET, "192.168.1.42", "255.255.255.0")],
    }

    with patch("subnet_detect.socket.socket", return_value=fake_sock), \
         patch("subnet_detect.psutil.net_if_addrs", return_value=fake_if_addrs):
        cidr = detect_local_cidr()

    assert cidr == "192.168.1.0/24"


def test_raises_when_no_default_route():
    fake_sock = MagicMock()
    fake_sock.connect.side_effect = OSError("network unreachable")
    fake_sock.__enter__.return_value = fake_sock

    with patch("subnet_detect.socket.socket", return_value=fake_sock), \
         pytest.raises(SubnetDetectionError):
        detect_local_cidr()


def test_raises_when_no_interface_matches_local_ip():
    fake_sock = MagicMock()
    fake_sock.getsockname.return_value = ("10.0.0.5", 0)
    fake_sock.__enter__.return_value = fake_sock

    with patch("subnet_detect.socket.socket", return_value=fake_sock), \
         patch("subnet_detect.psutil.net_if_addrs", return_value={}), \
         pytest.raises(SubnetDetectionError):
        detect_local_cidr()


def test_detects_interface_name_for_matching_local_ip():
    fake_sock = MagicMock()
    fake_sock.getsockname.return_value = ("192.168.1.42", 0)
    fake_sock.__enter__.return_value = fake_sock

    fake_if_addrs = {
        "lo0": [_fake_addr(socket.AF_INET, "127.0.0.1", "255.0.0.0")],
        "en0": [_fake_addr(socket.AF_INET, "192.168.1.42", "255.255.255.0")],
    }

    with patch("subnet_detect.socket.socket", return_value=fake_sock), \
         patch("subnet_detect.psutil.net_if_addrs", return_value=fake_if_addrs):
        interface = detect_local_interface()

    assert interface == "en0"
