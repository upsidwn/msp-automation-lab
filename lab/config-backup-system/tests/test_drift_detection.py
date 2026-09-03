import os
import shutil
import subprocess

import pytest
import yaml

SOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "source")


def _load(relative_path):
    with open(os.path.join(SOURCE_DIR, relative_path)) as f:
        return yaml.safe_load(f)


def _syntax_check(playbook, tmp_path, extra_args=None):
    inventory = tmp_path / "hosts.yml"
    with open(os.path.join(SOURCE_DIR, "inventory", "hosts.yml.example")) as f:
        inventory.write_text(f.read())

    return subprocess.run(
        ["ansible-playbook", playbook, "--syntax-check", "-i", str(inventory)] + (extra_args or []),
        cwd=SOURCE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )


def test_set_baseline_targets_exos_group():
    playbook = _load("set_baseline.yml")

    play = playbook[0]
    assert play["hosts"] == "exos"


def test_set_baseline_refuses_to_run_without_explicit_confirmation():
    playbook = _load("set_baseline.yml")
    tasks = playbook[0]["tasks"]

    fail_tasks = [task for task in tasks if "ansible.builtin.fail" in task]
    assert len(fail_tasks) == 1
    assert fail_tasks[0]["when"] == "not (confirm_baseline_update | default(false) | bool)"


def test_set_baseline_saves_to_known_good_directory():
    playbook = _load("set_baseline.yml")
    tasks = playbook[0]["tasks"]

    copy_tasks = [task for task in tasks if "ansible.builtin.copy" in task]
    assert len(copy_tasks) == 1
    assert "known_good" in copy_tasks[0]["ansible.builtin.copy"]["dest"]


@pytest.mark.skipif(shutil.which("ansible-playbook") is None, reason="ansible-core not installed")
def test_set_baseline_passes_ansible_syntax_check(tmp_path):
    # Uses the committed .example inventory, never the real (gitignored)
    # one - only proves the YAML/module structure is valid, no real
    # device or real credentials involved.
    result = _syntax_check("set_baseline.yml", tmp_path)
    assert result.returncode == 0, result.stderr


def test_check_drift_targets_exos_group():
    playbook = _load("check_drift.yml")

    play = playbook[0]
    assert play["hosts"] == "exos"


def test_check_drift_fails_loud_when_no_baseline_exists():
    playbook = _load("check_drift.yml")
    tasks = playbook[0]["tasks"]

    fail_tasks = [task for task in tasks if "ansible.builtin.fail" in task]
    assert len(fail_tasks) == 1
    assert fail_tasks[0]["when"] == "not baseline_file.stat.exists"


def test_check_drift_treats_diff_rc_1_as_expected_not_a_failure():
    # diff's own exit codes: 0 = identical, 1 = differences found (the
    # normal "drift found" case), 2+ = a real error. Only 2+ should
    # ever fail the task.
    playbook = _load("check_drift.yml")
    tasks = playbook[0]["tasks"]

    diff_tasks = [task for task in tasks if "ansible.builtin.command" in task]
    assert len(diff_tasks) == 1
    assert diff_tasks[0]["failed_when"] == "drift_result.rc not in [0, 1]"
    assert diff_tasks[0]["changed_when"] is False


def test_check_drift_cleans_up_its_temp_file():
    playbook = _load("check_drift.yml")
    tasks = playbook[0]["tasks"]

    cleanup_tasks = [
        task
        for task in tasks
        if "ansible.builtin.file" in task and task["ansible.builtin.file"].get("state") == "absent"
    ]
    assert len(cleanup_tasks) == 1


@pytest.mark.skipif(shutil.which("ansible-playbook") is None, reason="ansible-core not installed")
def test_check_drift_passes_ansible_syntax_check(tmp_path):
    result = _syntax_check("check_drift.yml", tmp_path)
    assert result.returncode == 0, result.stderr
