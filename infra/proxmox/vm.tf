# k3s node: cloned from the ubuntu-24.04 cloud-init template (vm_id
# 9000) instead of a manual OS install. Doesn't touch docker-01 -
# separate VM, existing infra left alone. Bumped memory over the
# original learning_vm baseline (2048) to give k3s + the collector's
# CronJob pods real headroom instead of running right at the edge.
resource "proxmox_virtual_environment_vm" "k3s_node" {
  name      = "k3s-01"
  node_name = "proxmox1"
  vm_id     = 200

  clone {
    vm_id = 9000
  }

  cpu {
    cores = 2
  }

  memory {
    dedicated = 4096
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

output "k3s_node_ipv4" {
  value = proxmox_virtual_environment_vm.k3s_node.ipv4_addresses
}
