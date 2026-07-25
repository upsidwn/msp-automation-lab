# Looks up a MAC's manufacturer via its OUI (the IEEE-assigned first 3
# bytes). Uses the mac-vendor-lookup package rather than hand-vendoring
# the IEEE registry ourselves -- same "lean on existing, maintained
# tools" approach as nmap/snmpwalk elsewhere in this project. Downloads
# and caches the registry locally on first use; works offline after
# that -- worth knowing for a fully air-gapped deployment, not a
# blocker otherwise.

from mac_vendor_lookup import MacLookup, VendorNotFoundError

_lookup = None


def get_vendor(mac):
    global _lookup

    if not mac:
        return None

    if _lookup is None:
        _lookup = MacLookup()

    try:
        return _lookup.lookup(mac)
    except VendorNotFoundError:
        return None
