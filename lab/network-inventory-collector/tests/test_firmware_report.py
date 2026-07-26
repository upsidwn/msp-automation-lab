import csv
import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from firmware_report import (
    check_compliance,
    load_all_records,
    load_known_good,
    main,
    print_report,
    write_csv,
)


def _record(vendor, host, firmware, collected_at, **extra):
    return {
        "vendor": vendor,
        "host": host,
        "hostname": None,
        "model": "some-model",
        "firmware": firmware,
        "serial": "fake-serial",
        "collected_at": collected_at,
        **extra,
    }


def test_loads_discover_results_shape(tmp_path):
    (tmp_path / "discover_results.json").write_text(json.dumps({
        "records": [_record("juniper", "10.0.0.1", "21.4R3.15", "2026-01-01T00:00:00Z")],
        "unidentified": [{"ip": "10.0.0.99"}],
    }))

    records = load_all_records(str(tmp_path))

    assert len(records) == 1
    assert records[0]["firmware"] == "21.4R3.15"


def test_loads_plain_list_shape(tmp_path):
    (tmp_path / "inventory_run.json").write_text(json.dumps(
        [_record("extreme", "10.0.0.2", "30.7.1.4", "2026-01-01T00:00:00Z")]
    ))

    records = load_all_records(str(tmp_path))

    assert len(records) == 1
    assert records[0]["vendor"] == "extreme"


def test_loads_single_dict_shape(tmp_path):
    (tmp_path / "juniper_inventory.json").write_text(json.dumps(
        _record("juniper", "10.0.0.3", "21.4R3.15", "2026-01-01T00:00:00Z")
    ))

    records = load_all_records(str(tmp_path))

    assert len(records) == 1
    assert records[0]["host"] == "10.0.0.3"


def test_dedupes_same_device_across_files_keeping_latest():
    old = _record("juniper", "10.0.0.1", "21.4R3.14", "2026-01-01T00:00:00Z")
    new = _record("juniper", "10.0.0.1", "21.4R3.15", "2026-06-01T00:00:00Z")

    with patch("firmware_report._records_from_file", side_effect=[[old], [new]]), \
         patch("firmware_report.glob.glob", return_value=["a.json", "b.json"]):
        records = load_all_records("/fake")

    assert len(records) == 1
    assert records[0]["firmware"] == "21.4R3.15"


def test_dedupes_unifi_by_mac_not_shared_controller_host():
    ap1 = _record("unifi", "192.0.2.1", "6.5.55", "2026-01-01T00:00:00Z", mac_address="aa:bb:cc:00:00:01")
    ap2 = _record("unifi", "192.0.2.1", "6.5.55", "2026-01-01T00:00:00Z", mac_address="aa:bb:cc:00:00:02")

    with patch("firmware_report._records_from_file", return_value=[ap1, ap2]), \
         patch("firmware_report.glob.glob", return_value=["unifi_inventory.json"]):
        records = load_all_records("/fake")

    assert len(records) == 2


def test_load_known_good_missing_file_returns_empty(tmp_path):
    assert load_known_good(str(tmp_path / "nope.json")) == {}


def test_check_compliance_ok_when_version_matches():
    record = _record("juniper", "10.0.0.1", "21.4R3.15", "2026-01-01T00:00:00Z")
    known_good = {"juniper": ["21.4R3.15"]}

    assert check_compliance(record, known_good) == "ok"


def test_check_compliance_outdated_when_version_not_in_list():
    record = _record("juniper", "10.0.0.1", "21.4R3.9", "2026-01-01T00:00:00Z")
    known_good = {"juniper": ["21.4R3.15"]}

    assert check_compliance(record, known_good) == "OUTDATED"


def test_check_compliance_unknown_when_vendor_not_in_list():
    record = _record("juniper", "10.0.0.1", "21.4R3.15", "2026-01-01T00:00:00Z")

    assert check_compliance(record, {}) == "unknown"


def test_print_report_handles_empty(capsys):
    print_report([])

    assert "No collected inventory found" in capsys.readouterr().out


def test_print_report_includes_every_device_and_compliance(capsys):
    records = [
        _record("juniper", "10.0.0.1", "21.4R3.15", "2026-01-01T00:00:00Z"),
        _record("extreme", "10.0.0.2", "30.7.1.9", "2026-01-01T00:00:00Z"),
    ]
    known_good = {"juniper": ["21.4R3.15"], "extreme": ["30.7.1.4"]}

    print_report(records, known_good)
    out = capsys.readouterr().out

    assert "10.0.0.1" in out and "ok" in out
    assert "10.0.0.2" in out and "OUTDATED" in out


def test_write_csv_includes_all_fields_and_compliance(tmp_path):
    records = [_record("juniper", "10.0.0.1", "21.4R3.15", "2026-01-01T00:00:00Z")]
    known_good = {"juniper": ["21.4R3.15"]}
    out_path = tmp_path / "firmware_report.csv"

    write_csv(records, str(out_path), known_good)

    with open(out_path, newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["firmware"] == "21.4R3.15"
    assert rows[0]["compliance"] == "ok"


def test_main_skips_save_when_declined():
    records = [_record("juniper", "10.0.0.1", "21.4R3.15", "2026-01-01T00:00:00Z")]

    with patch("firmware_report.load_all_records", return_value=records), \
         patch("firmware_report.load_known_good", return_value={}), \
         patch("builtins.input", return_value="n"), \
         patch("firmware_report.write_csv") as mock_write:
        main()

    mock_write.assert_not_called()


def test_main_saves_when_confirmed():
    records = [_record("juniper", "10.0.0.1", "21.4R3.15", "2026-01-01T00:00:00Z")]

    with patch("firmware_report.load_all_records", return_value=records), \
         patch("firmware_report.load_known_good", return_value={}), \
         patch("builtins.input", return_value="y"), \
         patch("firmware_report.write_csv") as mock_write:
        main()

    mock_write.assert_called_once()


def test_main_does_not_prompt_when_nothing_collected():
    with patch("firmware_report.load_all_records", return_value=[]), \
         patch("firmware_report.load_known_good", return_value={}), \
         patch("builtins.input", side_effect=AssertionError("should never prompt")):
        main()
