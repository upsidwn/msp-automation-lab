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

    hosts = inventory["all"]["children"]["junos"]["hosts"]
    assert "ansible_host" in next(iter(hosts.values()))


def test_junos_group_vars_reference_vaulted_credentials():
    group_vars = _load("group_vars/junos/vars.yml")

    assert group_vars["ansible_user"] == "{{ vault_junos_user }}"
    assert group_vars["ansible_password"] == "{{ vault_junos_password }}"
    assert group_vars["ansible_network_os"] == "juniper.device.junos"


def test_example_vault_file_has_the_vars_group_vars_expects():
    vault_example = _load("group_vars/junos/vault.yml.example")

    assert "vault_junos_user" in vault_example
    assert "vault_junos_password" in vault_example


def test_backup_playbook_targets_junos_group_with_backup_task():
    playbook = _load("backup.yml")

    play = playbook[0]
    assert play["hosts"] == "junos"

    backup_tasks = [task for task in play["tasks"] if "juniper.device.junos_config" in task]
    assert len(backup_tasks) == 1
    assert backup_tasks[0]["juniper.device.junos_config"]["backup"] is True


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
