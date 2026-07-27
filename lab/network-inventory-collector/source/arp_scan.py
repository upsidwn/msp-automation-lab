# Active ARP sweep across a subnet using arp-scan, finds live hosts that
# nmap's port-based approach never sees at all, since answering an ARP
# request needs no open port whatsoever. Complements the passive mDNS
# listener the same way: another source of candidates discover.py
# wouldn't otherwise have.
#
# Confirmed live: arp-scan's raw-socket access sometimes just works
# unprivileged (this dev machine already had BPF device access from an
# earlier Wireshark install) and sometimes doesn't, depending on the
# machine's own setup. So this tries without sudo first and only
# escalates if that genuinely fails, rather than always prompting,
# matching the project's minimal-friction privilege model.
#
# Also confirmed live: arp-scan's own interface auto-detection picked a
# virtual interface with no IP on this Mac, so the interface always gets
# passed explicitly (via subnet_detect.detect_local_interface()) rather
# than left to arp-scan to guess.
#
# The unprivileged attempt streams results line by line as hosts
# respond (same background-thread-per-stream shape nmap_scan.py already
# uses for its own progress streaming, just stdout instead of stderr
# here), so a caller can show live progress instead of waiting for the
# whole sweep to finish. The sudo-elevated retry stays a single blocking
# call, results all land at once when it completes. Streaming that
# path too would mean teaching privilege.py about line-by-line reading
# for what's the less common path on a machine already set up like this
# one, not worth it unless something actually needs it.

import subprocess
import threading

import privilege
from subnet_detect import detect_local_interface

FORMAT = "${ip}\t${mac}\t${vendor}"


def _build_cmd(cidr, interface):
    return ["arp-scan", "--plain", "--ignoredups", f"--format={FORMAT}", "--interface", interface, cidr]


def _clean(text):
    """Strips control/non-printable characters. The vendor string comes
    from arp-scan's own local OUI reference file rather than anything a
    device sends directly, lower risk than mDNS's freely-chosen hostname
    field, but it still ends up printed to a terminal, so scrub it the
    same way for consistency.
    """
    return "".join(ch for ch in text if ch.isprintable())


def _parse_line(line):
    line = line.strip()
    if not line:
        return None

    parts = line.split("\t")
    if len(parts) != 3:
        return None

    ip, mac, vendor = parts
    vendor = _clean(vendor)
    return {"ip": ip, "mac": mac, "vendor": None if vendor.startswith("(Unknown") else vendor}


def parse_output(text):
    """Parses arp-scan's --plain tab-separated output into candidate
    dicts. One line per responding host: ip, mac, vendor (arp-scan's own
    OUI-based guess, None when it can't tell, e.g. "(Unknown)" or
    "(Unknown: locally administered)" for a randomized MAC).
    """
    candidates = []
    for line in text.splitlines():
        candidate = _parse_line(line)
        if candidate:
            candidates.append(candidate)

    return candidates


def _stream_and_parse(cmd, on_found):
    """Runs cmd, parsing and reporting each host as its line arrives
    instead of waiting for the whole scan to finish. Reads stderr on its
    own thread while the main thread reads stdout, same reasoning as
    nmap_scan.py's own streaming: reading both from the same thread (or
    via subprocess.run's capture, which does the same internally) risks
    a full pipe buffer on one stream blocking the other.
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    stderr_chunks = []
    stderr_thread = threading.Thread(target=lambda: stderr_chunks.append(proc.stderr.read()))
    stderr_thread.start()

    candidates = []
    for line in iter(proc.stdout.readline, ""):
        candidate = _parse_line(line)
        if candidate:
            candidates.append(candidate)
            if on_found:
                on_found(candidate)

    proc.stdout.close()
    stderr_thread.join()
    proc.stderr.close()
    proc.wait()

    return proc.returncode, "".join(stderr_chunks), candidates


def scan(cidr, interface=None, on_found=None):
    """Runs arp-scan against cidr, trying without elevated privileges
    first and only falling back to a sudo prompt if that genuinely
    fails. Returns None if elevation was needed and declined.

    on_found, if given, gets called with each candidate as arp-scan
    reports it during the unprivileged attempt, for a live view instead
    of waiting for the whole sweep to finish.
    """
    interface = interface or detect_local_interface()
    cmd = _build_cmd(cidr, interface)

    returncode, stderr, candidates = _stream_and_parse(cmd, on_found)
    if returncode == 0 and "permission" not in stderr.lower():
        return candidates

    output = privilege.confirm_and_run_with_sudo(cmd, reason="send raw ARP requests across the subnet")
    if output is None:
        return None

    return parse_output(output)
