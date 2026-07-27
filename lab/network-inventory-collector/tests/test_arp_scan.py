import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import arp_scan

# Real arp-scan --plain --ignoredups output, tab-separated, hand-typed to
# match the format confirmed live against a real subnet. Not a real
# capture, every value here is fake.
SAMPLE_OUTPUT = (
    "10.0.0.1\taa:bb:cc:dd:ee:01\tSome Vendor Inc.\n"
    "10.0.0.2\taa:bb:cc:dd:ee:02\t(Unknown)\n"
    "10.0.0.3\taa:bb:cc:dd:ee:03\t(Unknown: locally administered)\n"
)


def test_parse_output_returns_one_candidate_per_line():
    candidates = arp_scan.parse_output(SAMPLE_OUTPUT)

    assert len(candidates) == 3
    assert {c["ip"] for c in candidates} == {"10.0.0.1", "10.0.0.2", "10.0.0.3"}


def test_parse_output_keeps_known_vendor():
    candidates = arp_scan.parse_output(SAMPLE_OUTPUT)

    by_ip = {c["ip"]: c for c in candidates}
    assert by_ip["10.0.0.1"]["vendor"] == "Some Vendor Inc."
    assert by_ip["10.0.0.1"]["mac"] == "aa:bb:cc:dd:ee:01"


def test_parse_output_normalizes_unknown_vendor_variants_to_none():
    candidates = arp_scan.parse_output(SAMPLE_OUTPUT)

    by_ip = {c["ip"]: c for c in candidates}
    assert by_ip["10.0.0.2"]["vendor"] is None
    assert by_ip["10.0.0.3"]["vendor"] is None


def test_parse_output_returns_empty_for_no_output():
    assert arp_scan.parse_output("") == []


def test_parse_output_strips_control_characters_from_vendor():
    hostile = "10.0.0.4\taa:bb:cc:dd:ee:04\tEvil\x1b[31mVendor\n"

    candidates = arp_scan.parse_output(hostile)

    assert "\x1b" not in candidates[0]["vendor"]


def test_parse_output_skips_malformed_lines():
    assert arp_scan.parse_output("not enough fields here\n") == []


def _fake_popen(stdout_lines, stderr_text="", returncode=0):
    """A MagicMock standing in for subprocess.Popen: readline() yields
    each line then "" (the sentinel iter(readline, "") in _stream_and_parse
    stops on), stderr.read() returns the whole stderr text at once.
    """
    proc = MagicMock()
    lines = iter(stdout_lines + [""])
    proc.stdout.readline.side_effect = lambda: next(lines)
    proc.stderr.read.return_value = stderr_text
    proc.returncode = returncode
    return proc


SAMPLE_LINES = [
    "10.0.0.1\taa:bb:cc:dd:ee:01\tSome Vendor Inc.\n",
    "10.0.0.2\taa:bb:cc:dd:ee:02\t(Unknown)\n",
    "10.0.0.3\taa:bb:cc:dd:ee:03\t(Unknown: locally administered)\n",
]


def test_scan_uses_result_directly_when_unprivileged_succeeds():
    fake_proc = _fake_popen(SAMPLE_LINES)

    with patch("arp_scan.subprocess.Popen", return_value=fake_proc) as mock_popen, \
         patch("arp_scan.privilege.confirm_and_run_with_sudo") as mock_sudo:
        candidates = arp_scan.scan("10.0.0.0/24", interface="en0")

    assert len(candidates) == 3
    mock_sudo.assert_not_called()
    called_cmd = mock_popen.call_args.args[0]
    assert called_cmd[0] == "arp-scan"
    assert "--interface" in called_cmd and "en0" in called_cmd


def test_scan_calls_on_found_as_each_host_streams_in():
    fake_proc = _fake_popen(SAMPLE_LINES)
    found = []

    with patch("arp_scan.subprocess.Popen", return_value=fake_proc):
        arp_scan.scan("10.0.0.0/24", interface="en0", on_found=found.append)

    assert [c["ip"] for c in found] == ["10.0.0.1", "10.0.0.2", "10.0.0.3"]


def test_scan_falls_back_to_sudo_on_nonzero_exit():
    fake_proc = _fake_popen([], stderr_text="you don't have permission to capture", returncode=1)

    with patch("arp_scan.subprocess.Popen", return_value=fake_proc), \
         patch("arp_scan.privilege.confirm_and_run_with_sudo", return_value=SAMPLE_OUTPUT) as mock_sudo:
        candidates = arp_scan.scan("10.0.0.0/24", interface="en0")

    assert len(candidates) == 3
    mock_sudo.assert_called_once()


def test_scan_returns_none_when_sudo_declined():
    fake_proc = _fake_popen([], stderr_text="permission denied", returncode=1)

    with patch("arp_scan.subprocess.Popen", return_value=fake_proc), \
         patch("arp_scan.privilege.confirm_and_run_with_sudo", return_value=None):
        result = arp_scan.scan("10.0.0.0/24", interface="en0")

    assert result is None


def test_scan_detects_interface_when_not_given():
    fake_proc = _fake_popen([])

    with patch("arp_scan.subprocess.Popen", return_value=fake_proc) as mock_popen, \
         patch("arp_scan.detect_local_interface", return_value="en0"):
        arp_scan.scan("10.0.0.0/24")

    called_cmd = mock_popen.call_args.args[0]
    assert "en0" in called_cmd


def test_stream_and_parse_reads_real_subprocess_stdout_and_stderr_concurrently():
    # Real subprocess, not mocked, the exact concurrency shape (one
    # thread reading stderr while the main thread reads stdout) that
    # nmap_scan.py's own streaming already had to get right, so this
    # covers the same class of bug for arp_scan's version of it.
    script = (
        "import sys\n"
        "for i in range(20):\n"
        "    print(f'noise {i}', file=sys.stderr)\n"
        "print('10.0.0.5\\taa:bb:cc:dd:ee:05\\tSome Vendor')\n"
    )
    returncode, stderr, candidates = arp_scan._stream_and_parse([sys.executable, "-c", script], None)

    assert returncode == 0
    assert "noise 19" in stderr
    assert candidates == [{"ip": "10.0.0.5", "mac": "aa:bb:cc:dd:ee:05", "vendor": "Some Vendor"}]
