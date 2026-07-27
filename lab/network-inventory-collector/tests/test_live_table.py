import io
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from live_table import LiveTable, _format_row, _truncate


def test_format_row_with_only_ip_known():
    assert _format_row({"ip": "10.0.0.1"}) == "10.0.0.1"


def test_format_row_with_status_only():
    row = {"ip": "10.0.0.2", "status": "scanning..."}
    assert _format_row(row) == "10.0.0.2 - scanning..."


def test_format_row_combines_multiple_fields_in_order():
    row = {"ip": "10.0.0.3", "vendor": "juniper", "model": "lab-switch-1"}
    assert _format_row(row) == "10.0.0.3 - juniper, lab-switch-1"


def test_format_row_includes_services_joined():
    row = {"ip": "10.0.0.4", "hostname": "thing.local", "services": ["_http._tcp.local.", "_ipp._tcp.local."]}
    assert _format_row(row) == "10.0.0.4 - thing.local, _http._tcp.local., _ipp._tcp.local."


def test_format_row_skips_empty_fields():
    row = {"ip": "10.0.0.5", "status": None, "vendor": "", "mac": "aa:bb:cc:dd:ee:ff"}
    assert _format_row(row) == "10.0.0.5 - aa:bb:cc:dd:ee:ff"


def test_upsert_creates_new_row_for_unseen_ip():
    stream = io.StringIO()
    table = LiveTable(stream=stream)

    table.upsert("10.0.0.1", status="scanning...")

    assert table._rows["10.0.0.1"] == {"ip": "10.0.0.1", "status": "scanning..."}


def test_upsert_merges_fields_into_existing_row():
    stream = io.StringIO()
    table = LiveTable(stream=stream)

    table.upsert("10.0.0.1", status="scanning...")
    table.upsert("10.0.0.1", vendor="juniper", model="lab-switch-1")

    assert table._rows["10.0.0.1"]["status"] == "scanning..."
    assert table._rows["10.0.0.1"]["vendor"] == "juniper"
    assert table._rows["10.0.0.1"]["model"] == "lab-switch-1"


def test_upsert_does_not_overwrite_existing_value_with_falsy_update():
    stream = io.StringIO()
    table = LiveTable(stream=stream)

    table.upsert("10.0.0.1", mac_vendor="Some Vendor")
    table.upsert("10.0.0.1", mac_vendor=None)

    assert table._rows["10.0.0.1"]["mac_vendor"] == "Some Vendor"


def test_non_tty_stream_prints_one_line_per_update():
    stream = io.StringIO()
    table = LiveTable(stream=stream)

    table.upsert("10.0.0.1", status="scanning...")
    table.upsert("10.0.0.2", status="scanning...")
    table.upsert("10.0.0.1", status="", vendor="juniper")

    lines = stream.getvalue().splitlines()
    assert lines == [
        "10.0.0.1 - scanning...",
        "10.0.0.2 - scanning...",
        "10.0.0.1 - juniper",
    ]


def test_upsert_with_empty_string_clears_a_field():
    stream = io.StringIO()
    table = LiveTable(stream=stream)

    table.upsert("10.0.0.1", status="scanning...")
    table.upsert("10.0.0.1", status="", vendor="juniper")

    assert _format_row(table._rows["10.0.0.1"]) == "10.0.0.1 - juniper"


def test_tty_stream_redraws_in_place_with_ansi_codes():
    stream = MagicMock()
    stream.isatty.return_value = True
    table = LiveTable(stream=stream)

    table.upsert("10.0.0.1", status="scanning...")
    stream.reset_mock()
    table.upsert("10.0.0.2", status="scanning...")

    written = "".join(call.args[0] for call in stream.write.call_args_list)
    assert "\033[1A" in written
    assert "10.0.0.1 - scanning..." in written
    assert "10.0.0.2 - scanning..." in written


def test_tty_stream_tracks_drawn_line_count_across_redraws():
    stream = MagicMock()
    stream.isatty.return_value = True
    table = LiveTable(stream=stream)

    table.upsert("10.0.0.1", status="scanning...")
    table.upsert("10.0.0.2", status="scanning...")
    table.upsert("10.0.0.3", status="scanning...")

    assert table._drawn_lines == 3


def test_truncate_leaves_short_text_alone():
    assert _truncate("10.0.0.1 - juniper", 80) == "10.0.0.1 - juniper"


def test_truncate_shortens_text_longer_than_width_with_ellipsis():
    text = "10.0.0.1 - " + "x" * 100
    result = _truncate(text, 40)

    assert len(result) == 40
    assert result.endswith("...")
    assert result.startswith("10.0.0.1 - ")


def test_truncate_handles_a_width_too_small_for_an_ellipsis():
    assert _truncate("10.0.0.1 - juniper", 2) == "10"


def test_truncate_handles_zero_or_negative_width_by_leaving_text_alone():
    assert _truncate("10.0.0.1 - juniper", 0) == "10.0.0.1 - juniper"
    assert _truncate("10.0.0.1 - juniper", -5) == "10.0.0.1 - juniper"


def test_redraw_in_place_truncates_a_row_wider_than_the_terminal():
    # A long row that would wrap onto a second physical line if left
    # untruncated, confirmed live this breaks the cursor-up-by-N-rows
    # math, since N stops matching the actual number of screen lines
    # once a row silently spans two of them.
    stream = MagicMock()
    stream.isatty.return_value = True
    table = LiveTable(stream=stream)

    long_services = [f"_service{i}._tcp.local." for i in range(20)]

    with patch("live_table.shutil.get_terminal_size", return_value=MagicMock(columns=40)):
        table.upsert("10.0.0.1", hostname="thing.local", services=long_services)

    written_lines = [
        call.args[0] for call in stream.write.call_args_list if call.args[0].startswith("\033[2K")
    ]
    assert len(written_lines) == 1
    line_content = written_lines[0][len("\033[2K"):].rstrip("\n")
    assert len(line_content) <= 40
    assert line_content.endswith("...")


def test_redraw_in_place_does_not_truncate_a_row_that_fits():
    stream = MagicMock()
    stream.isatty.return_value = True
    table = LiveTable(stream=stream)

    with patch("live_table.shutil.get_terminal_size", return_value=MagicMock(columns=80)):
        table.upsert("10.0.0.1", vendor="juniper")

    written_lines = [
        call.args[0] for call in stream.write.call_args_list if call.args[0].startswith("\033[2K")
    ]
    assert written_lines[0] == "\033[2K10.0.0.1 - juniper\n"
