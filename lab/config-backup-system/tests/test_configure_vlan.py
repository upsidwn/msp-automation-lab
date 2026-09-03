import os
import shutil
import subprocess

import pytest
import yaml

SOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "source")


def _load(relative_path):
    with open(os.path.join(SOURCE_DIR, relative_path)) as f:
        return yaml.safe_load(f)


def test_configure_vlan_playbook_targets_exos_group():
    playbook = _load("configure_vlan.yml")

    play = playbook[0]
    assert play["hosts"] == "exos"


def test_configure_vlan_creates_the_vlan_only_when_it_doesnt_already_exist():
    # create vlan is a one-shot action, not a declarative line cli_config
    # can diff against the running config - confirmed live it re-sends
    # it every run and the device rejects the duplicate. Hand-rolled
    # idempotency instead: gated on a fact computed from the pre-change
    # snapshot, not left to cli_config.
    playbook = _load("configure_vlan.yml")
    tasks = playbook[0]["tasks"]

    fact_tasks = [task for task in tasks if "ansible.builtin.set_fact" in task]
    assert len(fact_tasks) == 1
    assert fact_tasks[0]["ansible.builtin.set_fact"]["vlan_already_exists"] == "{{ vlan_name in pre_change_vlans.stdout }}"

    create_tasks = [
        task
        for task in tasks
        if "ansible.netcommon.cli_command" in task and task["ansible.netcommon.cli_command"].get("command") == "create vlan {{ vlan_name }}"
    ]
    assert len(create_tasks) == 1
    assert create_tasks[0]["when"] == "not vlan_already_exists and not ansible_check_mode"
    assert create_tasks[0]["notify"] == "Persist the change"


def test_configure_vlan_pushes_tag_and_port_config_via_cli_config():
    playbook = _load("configure_vlan.yml")
    tasks = playbook[0]["tasks"]

    config_tasks = [task for task in tasks if "ansible.netcommon.cli_config" in task]
    assert len(config_tasks) == 1

    config = config_tasks[0]["ansible.netcommon.cli_config"]["config"]
    assert "create vlan" not in config
    assert "tag" in config
    assert "add ports" in config
    assert config_tasks[0]["notify"] == "Persist the change"


def test_configure_vlan_only_saves_via_a_notified_handler():
    # A handler only ever fires when something notifies it - either the
    # create task or the cli_config task, whichever actually changed
    # something. A fully no-op run never touches non-volatile storage.
    playbook = _load("configure_vlan.yml")
    handlers = playbook[0]["handlers"]

    save_handlers = [
        handler
        for handler in handlers
        if "ansible.netcommon.cli_command" in handler and handler["ansible.netcommon.cli_command"].get("command") == "save configuration"
    ]
    assert len(save_handlers) == 1
    assert save_handlers[0]["name"] == "Persist the change"


def test_configure_vlan_verifies_the_port_landed_in_the_vlan():
    playbook = _load("configure_vlan.yml")
    tasks = playbook[0]["tasks"]

    assert_tasks = [task for task in tasks if "ansible.builtin.assert" in task]
    assert len(assert_tasks) == 1
    assert "vlan_port in post_change_vlan.stdout" in assert_tasks[0]["ansible.builtin.assert"]["that"]


@pytest.mark.skipif(shutil.which("ansible-playbook") is None, reason="ansible-core not installed")
def test_configure_vlan_passes_ansible_syntax_check(tmp_path):
    # Uses the committed .example inventory, never the real (gitignored)
    # one - this only proves the YAML/module structure is valid, no real
    # device or real credentials involved. Extra-vars are dummy values,
    # syntax-check doesn't evaluate them against a real device either way.
    inventory = tmp_path / "hosts.yml"
    with open(os.path.join(SOURCE_DIR, "inventory", "hosts.yml.example")) as f:
        inventory.write_text(f.read())

    result = subprocess.run(
        [
            "ansible-playbook",
            "configure_vlan.yml",
            "--syntax-check",
            "-i",
            str(inventory),
            "-e",
            "vlan_name=test100",
            "-e",
            "vlan_id=100",
            "-e",
            "vlan_port=20",
        ],
        cwd=SOURCE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
