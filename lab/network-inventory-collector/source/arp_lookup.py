# Reads a host's MAC from the OS's own ARP cache -- works for any
# device on the same local subnet the box is already on, no elevated
# privileges needed. Relies on something having already talked to the
# host (nmap's own scan does this as a side effect of routing packets
# to it); returns None if there's no resolved entry yet, or the host
# isn't on this segment at all (routed traffic never reveals the far
# end's real MAC, no matter what privilege level you're running at).

import re
import subprocess

# macOS's `arp` output doesn't zero-pad single-digit hex octets (e.g.
# "64:0" instead of "64:00") -- match 1-2 hex digits per octet and
# normalize afterward rather than assuming a fixed-width MAC string.
MAC_PATTERN = re.compile(r"at ([0-9a-fA-F]{1,2}(?::[0-9a-fA-F]{1,2}){5})")


def get_mac(ip):
    """Confirmed live: a minimal container image without the `arp`
    command installed made this crash the entire scan, losing every
    already-collected result, instead of just leaving one candidate's
    MAC unknown. A missing lookup tool should degrade the same way a
    missing ARP cache entry already does, not take everything else down
    with it.
    """
    try:
        result = subprocess.run(["arp", "-n", ip], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None

    match = MAC_PATTERN.search(result.stdout)
    if not match:
        return None

    return ":".join(octet.zfill(2) for octet in match.group(1).split(":"))
