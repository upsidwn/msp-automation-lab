# Terraform - Proxmox

Provisions VMs on the Proxmox NUC as code instead of clicking through
the UI. Separate from `lab/`: this provisions the lab environment
itself, not an MSP-facing tool.

## Auth

Uses a scoped Proxmox API token (`terraform@pve!tf-token`), not root,
same least-privilege instinct as `privilege.py` in the collector. Role
grants only what VM provisioning needs (VM.Allocate, VM.Config.*,
Datastore.AllocateSpace, etc.) via a dedicated `TerraformProv` role and
`terraform@pve` user, created with `pveum` on the Proxmox host itself.

## Template

VMs get cloned from a cloud-init-ready Ubuntu 24.04 template (VM ID
9000), not installed from an ISO each time. One-time setup, not
Terraform-managed itself: download the Ubuntu cloud image, `qm create`
+ `qm importdisk` it in, attach a cloud-init drive, convert with `qm
template`. Includes `qemu-guest-agent`, needed for Terraform to read
back the VM's IP after cloning, see design-notes.md.

## Setup

```
cp .env.example .env   # fill in real endpoint + token
source .env
terraform init
```

## Status

Provider auth and the cloud-init template both confirmed live: full
`destroy` + `apply` cycle rebuilds a VM from scratch with a real IP
reported back on the first apply, no manual steps. See design-notes.md
for what it took to get there.

The VM resource itself started as a throwaway `learning_vm`
(`tf-learning-01`), later repurposed into `k3s_node` (`k3s-01`, see
`vm.tf`) once it needed a real purpose - the k3s cluster the
collector's CronJob runs on.
