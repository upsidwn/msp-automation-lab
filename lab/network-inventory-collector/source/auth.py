# Shared connection/auth logic across vendors. Tries a pool of known
# credentials against a device; if none work, prompts interactively and
# appends the working credential to the pool for the rest of this run.
# Nothing here ever writes credentials to disk.

import getpass

from netmiko import ConnectHandler, NetmikoAuthenticationException
from netmiko.exceptions import NetmikoBaseException, SSHException


def try_ssh_device_types(host, pool, device_types):
    """Tries each device_type in turn against the pool -- never prompts.

    Built for discovery, where the vendor isn't known yet: guessing the
    wrong device_type against a host shouldn't stop and ask for a
    password. A wrong guess can fail in several different ways depending
    on how far it gets -- an auth failure, a connection-level timeout,
    or (confirmed live, against a real device) a ReadTimeout during
    session prep when a vendor-specific setup command doesn't match the
    device's actual prompt. Netmiko's exceptions split across two root
    classes (SSHException and NetmikoBaseException) rather than one
    common base, so both are caught here -- any Netmiko-originated
    failure just means "try the next guess," not "crash the scan."
    Returns (device_type, conn) on the first successful connection, or
    None if nothing worked.
    """
    for device_type in device_types:
        for cred in pool:
            try:
                conn = ConnectHandler(device_type=device_type, host=host, **cred)
                return device_type, conn
            except (SSHException, NetmikoBaseException):
                continue

    return None


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
