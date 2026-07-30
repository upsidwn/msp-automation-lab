provider "proxmox" {
  # Endpoint, API token, and TLS trust all come from environment
  # variables (PROXMOX_VE_ENDPOINT / PROXMOX_VE_API_TOKEN /
  # PROXMOX_VE_INSECURE), never hardcoded here. See .env.example.
}
