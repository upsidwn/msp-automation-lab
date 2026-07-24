import os


class MissingConfigError(Exception):
    pass


def load_juniper_config():
    required = {
        "host": "NIC_JUNOS_HOST",
        "username": "NIC_JUNOS_USER",
        "password": "NIC_JUNOS_PASS",
    }

    missing = [env_var for env_var in required.values() if not os.environ.get(env_var)]
    if missing:
        raise MissingConfigError(
            f"Missing required env vars: {', '.join(missing)}. "
            "Copy .env.example to .env and fill it in."
        )

    return {key: os.environ[env_var] for key, env_var in required.items()}
