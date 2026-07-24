# Shared connection/auth logic across vendors. Tries a pool of known
# credentials against a device; if none work, prompts interactively and
# appends the working credential to the pool for the rest of this run.
# Nothing here ever writes credentials to disk.

import getpass

from netmiko import ConnectHandler, NetmikoAuthenticationException


def connect_with_pool(device_type, host, pool):
    for cred in pool:
        try:
            return ConnectHandler(device_type=device_type, host=host, **cred)
        except NetmikoAuthenticationException:
            continue

    print(f"No known credentials worked for {host}.")
    while True:
        username = input(f"Username for {host}: ")
        password = getpass.getpass(f"Password for {host}: ")
        cred = {"username": username, "password": password}

        try:
            conn = ConnectHandler(device_type=device_type, host=host, **cred)
        except NetmikoAuthenticationException:
            print("Auth failed -- try again (Ctrl+C to give up).")
            continue

        pool.append(cred)
        return conn
