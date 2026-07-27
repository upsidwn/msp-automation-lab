# Passively listens for mDNS/DNS-SD announcements instead of probing for
# them, the complement to nmap_scan.py's active sweep. Catches
# self-announcing devices (smart speakers, printers, IoT gear) that
# don't have SSH/HTTP/HTTPS open at all, which nmap's port scan would
# never find regardless of probe type. Zero elevated privileges: this
# is a normal multicast socket listen, no raw packet crafting.
#
# SSDP (UPnP's own discovery protocol) is a separate wire format from
# mDNS/DNS-SD, and zeroconf doesn't speak it, so that's deferred, not
# folded in here, see design-notes.md.
#
# Two-phase, like dig'ing for records then resolving them: DNS-SD has no
# single "list everything" query, so first ask what service *types* are
# out there (`_services._dns-sd._udp.local.`), then browse for instances
# of each type found.

import time

from zeroconf import (
    IPVersion,
    ServiceBrowser,
    ServiceListener,
    Zeroconf,
    ZeroconfServiceTypes,
)


class _CollectingListener(ServiceListener):
    """Keyed by (service_type, name) so a later update doesn't duplicate
    an entry, and a removal (device went offline mid-listen) drops it.

    These callbacks fire for announcements from any device on the LAN,
    not just well-behaved ones. A crafted or malformed announcement can
    make zeroconf's own get_service_info() raise (confirmed against its
    source: a bad type/name pairing raises BadTypeInNameException, and
    nothing between the incoming packet and this callback catches it),
    so one bad record shouldn't be able to take down the whole listen.

    Also feeds each resolved service into merger (if given) as it
    arrives, so a caller can watch per-IP results build up live instead
    of waiting for the whole listen window to finish.
    """

    def __init__(self, merger=None):
        self.seen = {}
        self._merger = merger

    def add_service(self, zc, service_type, name):
        try:
            info = zc.get_service_info(service_type, name)
        except Exception:  # noqa: BLE001, untrusted device data, any exception type is possible
            return
        if info is not None:
            self.seen[(service_type, name)] = info
            if self._merger:
                self._merger.add(info)

    def update_service(self, zc, service_type, name):
        self.add_service(zc, service_type, name)

    def remove_service(self, zc, service_type, name):
        self.seen.pop((service_type, name), None)


def listen(duration=5, on_update=None):
    """Returns the raw ServiceInfo objects seen in `duration` seconds.
    Wall-clock cost is roughly duration plus a couple seconds up front
    for the service-type query, not exactly `duration`, fine for a tool
    that's already reporting progress live, not worth the complexity of
    carving the budget precisely.

    on_update, if given, gets called with that IP's current merged
    candidate (see merge_by_ip) every time a service resolves during
    the listen window, not just once at the end, for a live view of
    what's being found.
    """
    if duration <= 0:
        return []

    zc = Zeroconf()
    try:
        service_types = ZeroconfServiceTypes.find(zc=zc, timeout=3)
        if not service_types:
            return []

        merger = _IncrementalMerge(on_update)
        listener = _CollectingListener(merger)
        browser = ServiceBrowser(zc, list(service_types), listener=listener)
        try:
            time.sleep(duration)
        finally:
            browser.cancel()

        return list(listener.seen.values())
    finally:
        zc.close()


def _clean(text):
    """Strips control/non-printable characters from a value a device on
    the LAN gets to choose (hostname, service type). Nothing stops a
    hostile announcement from embedding terminal escape sequences or
    stray newlines in these fields, and they end up printed to a
    terminal, so scrub them before they go anywhere.
    """
    return "".join(ch for ch in text if ch.isprintable())


class _IncrementalMerge:
    """Same per-IP grouping merge_by_ip needs, done incrementally: feed
    it one ServiceInfo at a time and it keeps the running merged state,
    calling on_update with that IP's current snapshot each time it
    changes. merge_by_ip() is just this fed a whole batch with no
    callback, so there's one merge implementation, not two.
    """

    def __init__(self, on_update=None):
        self._by_ip = {}
        self._on_update = on_update

    def add(self, info):
        hostname = _clean((info.server or "").rstrip(".")) or None
        for ip in info.parsed_addresses(IPVersion.V4Only):
            if ip.startswith("127."):
                continue

            candidate = self._by_ip.setdefault(ip, {"ip": ip, "hostname": None, "services": set()})
            candidate["services"].add(_clean(info.type))
            if hostname and not candidate["hostname"]:
                candidate["hostname"] = hostname

            if self._on_update:
                self._on_update(self._snapshot(ip))

    def _snapshot(self, ip):
        candidate = self._by_ip[ip]
        return {"ip": candidate["ip"], "hostname": candidate["hostname"], "services": sorted(candidate["services"])}

    def result(self):
        return [self._snapshot(ip) for ip in self._by_ip]


def merge_by_ip(infos):
    """Collapses raw ServiceInfo entries into one candidate per IP, since
    a single device usually advertises more than one service (e.g. a
    printer announcing both _ipp._tcp and _http._tcp), and this project
    reports one record per device, not per service.

    Confirmed live: this machine's own services resolve to 127.0.0.1 as
    well as its real LAN IP, so loopback addresses get dropped here.
    That's just this box hearing itself, not a device on the network.
    """
    merger = _IncrementalMerge()
    for info in infos:
        merger.add(info)

    return merger.result()
