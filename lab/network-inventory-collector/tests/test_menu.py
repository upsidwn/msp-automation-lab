import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import menu
from menu import TOOLS, main, prompt_choice, run_tool
from subnet_detect import SubnetDetectionError


def test_prompt_choice_returns_selected_tool():
    with patch("builtins.input", return_value="2"):
        tool = prompt_choice()

    assert tool == TOOLS[1]


def test_prompt_choice_returns_none_on_quit():
    with patch("builtins.input", return_value="q"):
        tool = prompt_choice()

    assert tool is None


def test_prompt_choice_reprompts_on_invalid_input():
    with patch("builtins.input", side_effect=["nope", "0", "99", "1"]):
        tool = prompt_choice()

    assert tool == TOOLS[0]


def test_run_tool_invokes_correct_script_with_no_extra_args():
    tool = {"label": "test tool", "script": "collect.py", "needs": "nothing", "build_args": list}

    with patch("menu.subprocess.run") as mock_run:
        run_tool(tool)

    called_args, called_kwargs = mock_run.call_args
    assert called_args[0][0] == sys.executable
    assert called_args[0][1] == os.path.join(menu.SOURCE_DIR, "collect.py")
    assert called_args[0][2:] == []
    assert called_kwargs["env"]["PATH"] == os.environ["PATH"]


def test_run_tool_passes_through_build_args():
    tool = {
        "label": "test tool",
        "script": "discover.py",
        "needs": "nothing",
        "build_args": lambda: ["10.0.0.0/24", "--thorough"],
    }

    with patch("menu.subprocess.run") as mock_run:
        run_tool(tool)

    called_args = mock_run.call_args.args[0]
    assert called_args[2:] == ["10.0.0.0/24", "--thorough"]


def test_run_tool_injects_build_env_on_top_of_current_env():
    tool = {
        "label": "test tool",
        "script": "collect.py",
        "needs": "nothing",
        "build_args": list,
        "build_env": lambda: {"NIC_JUNOS_HOST": "10.0.0.9"},
    }

    with patch("menu.subprocess.run") as mock_run:
        run_tool(tool)

    called_env = mock_run.call_args.kwargs["env"]
    assert called_env["NIC_JUNOS_HOST"] == "10.0.0.9"
    assert called_env["PATH"] == os.environ["PATH"]


def test_discover_args_confirms_detected_subnet():
    with patch("menu.detect_local_cidr", return_value="192.168.1.0/24"), \
         patch("builtins.input", side_effect=["y", "n", "n"]):
        args = menu._discover_args()

    assert args == ["192.168.1.0/24"]


def test_discover_args_lets_user_override_detected_subnet():
    with patch("menu.detect_local_cidr", return_value="192.168.1.0/24"), \
         patch("builtins.input", side_effect=["n", "10.0.0.0/24", "n", "n"]):
        args = menu._discover_args()

    assert args == ["10.0.0.0/24"]


def test_discover_args_falls_back_to_manual_entry_when_detection_fails():
    with patch("menu.detect_local_cidr", side_effect=SubnetDetectionError("no route")), \
         patch("builtins.input", side_effect=["10.0.0.0/24", "n", "n"]):
        args = menu._discover_args()

    assert args == ["10.0.0.0/24"]


def test_discover_args_builds_both_flags():
    with patch("menu.detect_local_cidr", return_value="192.168.1.0/24"), \
         patch("builtins.input", side_effect=["y", "y", "y"]):
        args = menu._discover_args()

    assert args == ["192.168.1.0/24", "--thorough", "--prompt-on-auth-failure"]


def test_run_args_no_list_returns_no_args():
    with patch("builtins.input", return_value="n"):
        args = menu._run_args()

    assert args == []


def test_run_args_with_list_passes_devices_file():
    with patch("builtins.input", side_effect=["y", "/tmp/devices.csv"]):
        args = menu._run_args()

    assert args == ["--devices-file", "/tmp/devices.csv"]


def test_collect_env_uses_dotenv_by_default():
    with patch("builtins.input", return_value="y"):
        env = menu._collect_env()

    assert env == {}


def test_collect_env_prompts_for_override():
    with patch("builtins.input", side_effect=["n", "10.0.0.5", "admin"]), \
         patch("menu.getpass.getpass", return_value="pw"):
        env = menu._collect_env()

    assert env == {"NIC_JUNOS_HOST": "10.0.0.5", "NIC_CRED_1_USER": "admin", "NIC_CRED_1_PASS": "pw"}


def test_collect_unifi_env_prompts_for_override():
    with patch("builtins.input", side_effect=["n", "10.0.0.6"]), \
         patch("menu.getpass.getpass", return_value="fake-key"):
        env = menu._collect_unifi_env()

    assert env == {"NIC_UNIFI_HOST": "10.0.0.6", "NIC_UNIFI_API_KEY": "fake-key"}


def test_main_runs_one_tool_then_quits():
    with patch("builtins.input", side_effect=["4", "y", "n"]), \
         patch("menu.subprocess.run") as mock_run:
        main()

    assert mock_run.call_count == 1


def test_main_loops_until_told_to_stop():
    with patch("builtins.input", side_effect=["4", "y", "y", "4", "y", "n"]), \
         patch("menu.subprocess.run") as mock_run:
        main()

    assert mock_run.call_count == 2


def test_run_tool_calls_after_run_when_present():
    after_run = MagicMock()
    tool = {
        "label": "test tool",
        "script": "discover.py",
        "needs": "nothing",
        "build_args": list,
        "after_run": after_run,
    }

    with patch("menu.subprocess.run"):
        run_tool(tool)

    after_run.assert_called_once()


def test_run_tool_skips_after_run_when_absent():
    tool = {"label": "test tool", "script": "collect.py", "needs": "nothing", "build_args": list}

    with patch("menu.subprocess.run"):
        run_tool(tool)  # should not raise


def test_filter_and_report_prints_only_matching_vendor(tmp_path, capsys):
    results_file = tmp_path / "discover_results.json"
    results_file.write_text(json.dumps({
        "records": [
            {"vendor": "extreme", "model": "exos-fake", "hostname": "sw1", "host": "10.0.0.1"},
            {"vendor": "juniper", "model": "ex-fake", "hostname": "sw2", "host": "10.0.0.2"},
        ],
        "unidentified": [],
    }))

    with patch("menu.DISCOVER_OUTPUT", str(results_file)):
        menu._filter_and_report("extreme")

    out = capsys.readouterr().out
    assert "Extreme devices found: 1" in out
    assert "sw1" in out
    assert "sw2" not in out


def test_filter_and_report_handles_missing_results_file(tmp_path, capsys):
    with patch("menu.DISCOVER_OUTPUT", str(tmp_path / "nope.json")):
        menu._filter_and_report("extreme")

    assert "No scan results found" in capsys.readouterr().out


def test_main_exits_immediately_on_quit():
    with patch("builtins.input", return_value="q"), \
         patch("menu.subprocess.run") as mock_run:
        main()

    mock_run.assert_not_called()
