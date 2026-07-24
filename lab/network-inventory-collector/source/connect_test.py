# Throwaway connectivity check for the Juniper lab switch.
# Connects, runs `show version`, prints raw output. No parsing yet --
# just proving auth + reachability before building the real collector.

from dotenv import load_dotenv
from netmiko import NetmikoTimeoutException

from auth import connect_with_pool
from config import MissingConfigError, load_credential_pool, load_juniper_host

load_dotenv()


def main():
    try:
        host = load_juniper_host()
    except MissingConfigError as e:
        print(f"Config error: {e}")
        return

    pool = load_credential_pool()

    print(f"Connecting to {host}...")
    try:
        conn = connect_with_pool("juniper_junos", host, pool)
    except NetmikoTimeoutException:
        print(f"Timed out connecting to {host} -- check it's reachable and SSH is enabled.")
        return

    try:
        print(conn.send_command("show version"))
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
