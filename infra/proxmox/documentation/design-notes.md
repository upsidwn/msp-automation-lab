# Design notes - Terraform/Proxmox

## Auth

Scoped API token (`terraform@pve!tf-token`), not root, same
least-privilege instinct as `privilege.py` in the collector. Role
started minimal and grew by exactly one privilege the one time it
actually got denied (`VM.GuestAgent.Audit`, see below) rather than
guessing a broad set upfront.

## Real bugs found through live testing

Five things, each wrong in a way reasoning alone wouldn't have caught:

- **Role missing `VM.GuestAgent.Audit`**: first `apply` created the VM
  fine but errored waiting on the QEMU agent for network interfaces,
  an HTTP 403 from Proxmox. VM management privileges and guest-agent
  privileges are separate in Proxmox's permission model. Fixed by
  adding just that one privilege, not the broader
  `VM.GuestAgent.Unrestricted` Proxmox's error also offered, which
  additionally allows running commands/reading files through the
  agent.
- **`qemu-guest-agent` isn't preinstalled** on the official Ubuntu
  24.04 cloud image. Without it, `agent.enabled = true` in the
  resource just times out silently waiting for network data instead
  of failing clearly. Had to SSH in and install it manually, then bake
  that into the template so future clones don't repeat the same fix.
- **The agent channel itself was never enabled on the template's own
  config** - `--agent enabled=1` only ever got applied to actual VMs
  via Terraform's per-clone config, never to template 9000 during its
  original manual `qm` build. Surfaced as a different, clearer error
  ("No QEMU guest agent configured") than the permission/install
  issues above. Also confirmed live: this is boot-time QEMU device
  attachment, not hot-pluggable - a guest-level `reboot` doesn't pick
  it up, needs a full `qm shutdown` + `qm start`.
- **`qm template` marks the base disk read-only at the LVM layer**,
  separately from the `template: 1` config flag. Removing the flag
  alone to make the template editable again wasn't enough - QEMU
  refused to start it ("device is not writable") until the disk itself
  was flipped back with `lvchange -p rw`.
- **A `.env` line missing `export`** was invisible to `terraform`
  (a subprocess) while still readable via `echo` in the same
  interactive shell - zsh doesn't hand un-exported variables down to
  child processes. `echo $VAR` succeeding is not proof a subprocess
  can see it.

## Full clones, not linked

`clone.full` defaults to `true` in this setup, so each VM gets its own
independent disk copy at clone time. Confirmed useful in practice: let
the template be freely stopped, modified, and re-templated to fix the
guest-agent gap above without touching the VM already cloned from it.
