import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import privilege


def test_declining_returns_none_without_touching_sudo():
    with patch("builtins.input", return_value="n"), \
         patch("privilege.subprocess.run") as mock_run:
        result = privilege.confirm_and_run_with_sudo(["arp-scan", "10.0.0.0/24"], reason="test")

    assert result is None
    mock_run.assert_not_called()


def test_accepting_validates_sudo_then_runs_the_real_command():
    validate_result = MagicMock(returncode=0)
    run_result = MagicMock(returncode=0, stdout="the output")

    with patch("builtins.input", return_value="y"), \
         patch("privilege.subprocess.run", side_effect=[validate_result, run_result]) as mock_run:
        result = privilege.confirm_and_run_with_sudo(["arp-scan", "10.0.0.0/24"], reason="test")

    assert result == "the output"
    first_call_args = mock_run.call_args_list[0].args[0]
    second_call_args = mock_run.call_args_list[1].args[0]
    assert first_call_args == ["sudo", "-v"]
    assert second_call_args == ["sudo", "arp-scan", "10.0.0.0/24"]


def test_failed_sudo_validation_returns_none_without_running_the_command():
    validate_result = MagicMock(returncode=1)

    with patch("builtins.input", return_value="y"), \
         patch("privilege.subprocess.run", return_value=validate_result) as mock_run:
        result = privilege.confirm_and_run_with_sudo(["arp-scan", "10.0.0.0/24"], reason="test")

    assert result is None
    assert mock_run.call_count == 1


def test_failed_elevated_command_raises_called_process_error():
    validate_result = MagicMock(returncode=0)

    with patch("builtins.input", return_value="y"), \
         patch(
             "privilege.subprocess.run",
             side_effect=[validate_result, subprocess.CalledProcessError(1, ["sudo", "arp-scan"])],
         ):
        try:
            privilege.confirm_and_run_with_sudo(["arp-scan", "10.0.0.0/24"], reason="test")
            raised = False
        except subprocess.CalledProcessError:
            raised = True

    assert raised
