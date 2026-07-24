import os


class MissingConfigError(Exception):
    pass


def load_juniper_host():
    host = os.environ.get("NIC_JUNOS_HOST")
    if not host:
        raise MissingConfigError(
            "Missing required env var: NIC_JUNOS_HOST. "
            "Copy .env.example to .env and fill it in."
        )
    return host


def load_credential_pool(prefix="NIC_CRED"):
    """Loads NIC_CRED_1_USER/PASS, NIC_CRED_2_USER/PASS, ... in order,
    stopping at the first gap. Real customer networks rarely have one
    admin account that works everywhere -- this is the known-credential
    pool that auth.connect_with_pool() tries before falling back to an
    interactive prompt.
    """
    pool = []
    i = 1
    while True:
        username = os.environ.get(f"{prefix}_{i}_USER")
        password = os.environ.get(f"{prefix}_{i}_PASS")
        if not username or not password:
            break
        pool.append({"username": username, "password": password})
        i += 1

    return pool


def load_unifi_config():
    host = os.environ.get("NIC_UNIFI_HOST")
    api_key = os.environ.get("NIC_UNIFI_API_KEY")

    missing = [name for name, val in [("NIC_UNIFI_HOST", host), ("NIC_UNIFI_API_KEY", api_key)] if not val]
    if missing:
        raise MissingConfigError(
            f"Missing required env vars: {', '.join(missing)}. "
            "Copy .env.example to .env and fill it in."
        )

    return {"host": host, "api_key": api_key}
