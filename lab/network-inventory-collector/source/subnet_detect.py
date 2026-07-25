# Figures out the local machine's own subnet, for when discover.py isn't
# given an explicit CIDR. Same idea as `ip route get`/`route get` on the
# command line: ask the OS which interface would be used to reach the
# outside world, then read that interface's netmask. Uses psutil for the
# netmask lookup instead of hand-parsing `ifconfig`/`ip addr` text, which
# differs enough between macOS and Linux that it's not worth reimplementing.

import ipaddress
import socket

import psutil


class SubnetDetectionError(Exception):
    pass


def _local_ip():
    """Picks the local IP the OS would use to reach the outside world,
    without actually sending any traffic -- UDP connect() just asks the
    kernel to pick a route and a source address, nothing goes on the wire.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("8.8.8.8", 80))
        except OSError as e:
            raise SubnetDetectionError(
                "Could not determine a local IP -- no active network route found."
            ) from e
        return sock.getsockname()[0]


def _netmask_for_ip(ip):
    for addrs in psutil.net_if_addrs().values():
        for addr in addrs:
            if addr.family == socket.AF_INET and addr.address == ip:
                return addr.netmask

    raise SubnetDetectionError(f"Could not find a network interface matching {ip}.")


def detect_local_cidr():
    """Returns the CIDR of the network the local machine is actually on
    (the interface tied to its default route), e.g. "192.168.1.0/24".
    Raises SubnetDetectionError if it can't figure this out -- callers
    should fall back to asking for an explicit CIDR instead.
    """
    ip = _local_ip()
    netmask = _netmask_for_ip(ip)
    network = ipaddress.ip_network(f"{ip}/{netmask}", strict=False)

    return str(network)
