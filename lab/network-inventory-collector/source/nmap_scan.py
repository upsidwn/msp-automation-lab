# Runs nmap and parses its XML output into plain candidate dicts.
# Deliberately a plain TCP connect scan (-sT, not -sS) with no OS
# detection (-O), so this never needs sudo/raw sockets -- keeps it a
# normal user-run tool. Only scans the ports that matter for dispatch
# (SSH for the Junos/EXOS credential pool, HTTP/HTTPS for the UniFi API
# check). MAC address is often unavailable without elevated privileges
# -- callers should treat it as optional, not guaranteed.
#
# Discovery notes (confirmed live against a real /24): nmap's default
# host-discovery probes (ICMP + a couple of fixed ports) can miss real,
# reachable devices outright -- not a timing problem, a "wrong probe
# type" problem. Using SYN probes against our own target ports for
# discovery (-PS<ports>) instead of nmap's defaults fixed it, and found
# *more* live hosts overall, not just the one that was missing.
# --host-timeout caps how long any single slow host can eat into the
# whole scan. -Pn (skip discovery, port-scan every IP directly) is
# available as an explicit "thorough" opt-in -- confirmed live that one
# slow host alone can cost 190+ seconds under -Pn, so it's not a good
# default for a whole /24.

import subprocess
import threading
import xml.etree.ElementTree as ET

DEFAULT_PORTS = "22,80,443"


def _stream_progress(pipe):
    """Prints nmap's --stats-every lines live as the scan runs, instead
    of silently buffering them until the whole scan finishes.
    """
    for line in iter(pipe.readline, ""):
        line = line.strip()
        if line:
            print(f"  [nmap] {line}")
    pipe.close()


def _run_streaming(cmd):
    """Runs cmd, streaming stderr live via _stream_progress while
    capturing stdout to return whole. Reads each stream on its own file
    descriptor (main thread on stdout, the progress thread on stderr)
    rather than subprocess.communicate(), which tries to read both
    streams itself. That races against the progress thread already
    reading stderr and threw "Bad file descriptor", confirmed live
    against a real scan.
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    progress_thread = threading.Thread(target=_stream_progress, args=(proc.stderr,))
    progress_thread.start()

    stdout = proc.stdout.read()
    proc.stdout.close()
    proc.wait()
    progress_thread.join()

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)

    return stdout


def scan(cidr, ports=DEFAULT_PORTS, thorough=False):
    cmd = ["nmap", "-sT", "-sV", "--open", "-p", ports, "--stats-every", "10s"]

    if thorough:
        cmd += ["-Pn"]
    else:
        cmd += [f"-PS{ports}", "--host-timeout", "90s"]

    cmd += ["-oX", "-", cidr]

    return parse_xml(_run_streaming(cmd))


def parse_xml(xml_text):
    root = ET.fromstring(xml_text)
    candidates = []

    for host in root.findall("host"):
        ip = None
        mac = None
        for addr in host.findall("address"):
            if addr.get("addrtype") == "ipv4":
                ip = addr.get("addr")
            elif addr.get("addrtype") == "mac":
                mac = addr.get("addr")

        if not ip:
            continue

        open_ports = []
        ports_el = host.find("ports")
        if ports_el is not None:
            for port in ports_el.findall("port"):
                state = port.find("state")
                if state is None or state.get("state") != "open":
                    continue

                service = port.find("service")
                open_ports.append(
                    {
                        "port": int(port.get("portid")),
                        "protocol": port.get("protocol"),
                        "service": service.get("name") if service is not None else None,
                        "product": service.get("product") if service is not None else None,
                        "version": service.get("version") if service is not None else None,
                    }
                )

        candidates.append({"ip": ip, "mac": mac, "ports": open_ports})

    return candidates
