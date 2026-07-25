import os
import shutil
import subprocess

import pytest
import yaml

SOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "source")


def _load(relative_path):
    with open(os.path.join(SOURCE_DIR, relative_path)) as f:
        return yaml.safe_load(f)


def test_example_inventory_has_expected_shape():
    inventory = _load("inventory/hosts.yml.example")

    for group in ("junos", "exos"):
        hosts = inventory["all"]["children"][group]["hosts"]
        assert "ansible_host" in next(iter(hosts.values()))


def test_junos_group_vars_reference_vaulted_credentials():
    group_vars = _load("group_vars/junos/vars.yml")

    assert group_vars["ansible_user"] == "{{ vault_junos_user }}"
    assert group_vars["ansible_password"] == "{{ vault_junos_password }}"
    assert group_vars["ansible_network_os"] == "juniper.device.junos"


def test_exos_group_vars_reference_vaulted_credentials():
    group_vars = _load("group_vars/exos/vars.yml")

    assert group_vars["ansible_user"] == "{{ vault_exos_user }}"
    assert group_vars["ansible_password"] == "{{ vault_exos_password }}"
    assert group_vars["ansible_network_os"] == "community.network.exos"
    assert group_vars["ansible_connection"] == "ansible.netcommon.network_cli"


def test_example_vault_files_have_the_vars_each_group_vars_expects():
    junos_vault_example = _load("group_vars/junos/vault.yml.example")
    assert "vault_junos_user" in junos_vault_example
    assert "vault_junos_password" in junos_vault_example

    exos_vault_example = _load("group_vars/exos/vault.yml.example")
    assert "vault_exos_user" in exos_vault_example
    assert "vault_exos_password" in exos_vault_example


def test_backup_playbook_targets_junos_group_with_backup_task():
    playbook = _load("backup.yml")

    play = playbook[0]
    assert play["hosts"] == "junos"

    backup_tasks = [task for task in play["tasks"] if "juniper.device.junos_config" in task]
    assert len(backup_tasks) == 1
    assert backup_tasks[0]["juniper.device.junos_config"]["backup"] is True


def test_backup_playbook_targets_exos_group_with_show_config_and_copy():
    playbook = _load("backup.yml")

    play = playbook[1]
    assert play["hosts"] == "exos"

    cli_tasks = [task for task in play["tasks"] if "ansible.netcommon.cli_command" in task]
    assert len(cli_tasks) == 1
    assert cli_tasks[0]["ansible.netcommon.cli_command"]["command"] == "show config"

    copy_tasks = [task for task in play["tasks"] if "ansible.builtin.copy" in task]
    assert len(copy_tasks) == 1


@pytest.mark.skipif(shutil.which("ansible-playbook") is None, reason="ansible-core not installed")
def test_playbook_passes_ansible_syntax_check(tmp_path):
    # Uses the committed .example files, never the real (gitignored) ones --
    # this only proves the YAML/module structure is valid, no real device
    # or real credentials involved.
    inventory = tmp_path / "hosts.yml"
    inventory.write_text(open(os.path.join(SOURCE_DIR, "inventory", "hosts.yml.example")).read())

    result = subprocess.run(
        ["ansible-playbook", "backup.yml", "--syntax-check", "-i", str(inventory)],
        cwd=SOURCE_DIR,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
