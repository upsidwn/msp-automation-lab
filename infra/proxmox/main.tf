# Read-only connectivity check: proves the token can actually reach
# the Proxmox API and auth works, before any real VM resource exists.
data "proxmox_version" "current" {}

output "proxmox_version" {
  value = data.proxmox_version.current.version
}
