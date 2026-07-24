# Throwaway connectivity check for the Juniper lab switch.
# Connects, runs `show version`, prints raw output. No parsing yet --
# just proving auth + reachability before building the real collector.

from dotenv import load_dotenv
from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException

from config import load_juniper_config, MissingConfigError

load_dotenv()


def main():
    try:
        creds = load_juniper_config()
    except MissingConfigError as e:
        print(f"Config error: {e}")
        return

    device = {"device_type": "juniper_junos", **creds}

    print(f"Connecting to {device['host']}...")
    try:
        conn = ConnectHandler(**device)
    except NetmikoAuthenticationException:
        print("Auth failed -- check NIC_JUNOS_USER / NIC_JUNOS_PASS.")
        return
    except NetmikoTimeoutException:
        print(f"Timed out connecting to {device['host']} -- check it's reachable and SSH is enabled.")
        return

    try:
        print(conn.send_command("show version"))
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
