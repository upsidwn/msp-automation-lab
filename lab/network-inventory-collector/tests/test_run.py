import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from netmiko import NetmikoTimeoutException

from run import collect_one, load_devices_file, main


def test_load_devices_file_parses_vendor_host_pairs(tmp_path):
    devices_file = tmp_path / "devices.csv"
    devices_file.write_text("juniper,10.0.0.1\nexos,10.0.0.2\n")

    devices = load_devices_file(str(devices_file))

    assert devices == [("juniper", "10.0.0.1"), ("exos", "10.0.0.2")]


def test_load_devices_file_skips_header_row(tmp_path):
    devices_file = tmp_path / "devices.csv"
    devices_file.write_text("vendor,host\njuniper,10.0.0.1\n")

    devices = load_devices_file(str(devices_file))

    assert devices == [("juniper", "10.0.0.1")]


def test_load_devices_file_skips_blank_and_short_lines(tmp_path):
    devices_file = tmp_path / "devices.csv"
    devices_file.write_text("juniper,10.0.0.1\n\nexos\n")

    devices = load_devices_file(str(devices_file))

    assert devices == [("juniper", "10.0.0.1")]


def test_collect_one_returns_none_on_timeout():
    with patch("run.connect_with_pool", side_effect=NetmikoTimeoutException()):
        record = collect_one("juniper_junos", "10.0.0.1", MagicMock(), [])

    assert record is None


def test_collect_one_disconnects_after_collecting():
    fake_conn = MagicMock()
    fake_record = {"vendor": "juniper", "interfaces": []}
    collect_fn = MagicMock(return_value=fake_record)

    with patch("run.connect_with_pool", return_value=fake_conn):
        record = collect_one("juniper_junos", "10.0.0.1", collect_fn, [])

    assert record == fake_record
    fake_conn.disconnect.assert_called_once()


def test_main_with_devices_file_skips_interactive_prompt(tmp_path):
    devices_file = tmp_path / "devices.csv"
    devices_file.write_text("juniper,10.0.0.1\n")
    fake_record = {"vendor": "juniper", "model": "ex-fake", "interfaces": []}

    with patch("sys.argv", ["run.py", "--devices-file", str(devices_file)]), \
         patch("run.load_credential_pool", return_value=[]), \
         patch("run.collect_one", return_value=fake_record), \
         patch("builtins.input", side_effect=AssertionError("should never prompt")), \
         patch("builtins.open"), \
         patch("json.dump"):
        main()


def test_main_without_devices_file_uses_interactive_prompt():
    fake_record = {"vendor": "juniper", "model": "ex-fake", "interfaces": []}

    with patch("sys.argv", ["run.py"]), \
         patch("run.load_credential_pool", return_value=[]), \
         patch("run.prompt_device", return_value=("juniper_junos", "10.0.0.1", MagicMock())), \
         patch("run.collect_one", return_value=fake_record), \
         patch("builtins.input", return_value="n"), \
         patch("builtins.open"), \
         patch("json.dump"):
        main()
