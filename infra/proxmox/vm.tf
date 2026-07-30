# First real Terraform-provisioned VM: cloned from the ubuntu-24.04
# cloud-init template (vm_id 9000) instead of a manual OS install.
# Doesn't touch docker-01 - separate VM, existing infra left alone.
resource "proxmox_virtual_environment_vm" "learning_vm" {
  name      = "tf-learning-01"
  node_name = "proxmox1"
  vm_id     = 200

  clone {
    vm_id = 9000
  }

  cpu {
    cores = 2
  }

  memory {
    dedicated = 2048
  }

  agent {
    enabled = true
  }

  network_device {
    bridge = "vmbr0"
  }

  initialization {
    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }

    user_account {
      username = "ubuntu"
      keys     = [var.ssh_public_key]
    }
  }
}

output "learning_vm_ipv4" {
  value = proxmox_virtual_environment_vm.learning_vm.ipv4_addresses
}
