import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import oui_lookup
from mac_vendor_lookup import VendorNotFoundError


def test_get_vendor_returns_none_for_missing_mac():
    assert oui_lookup.get_vendor(None) is None


def test_get_vendor_returns_lookup_result():
    oui_lookup._lookup = None
    fake_lookup = MagicMock()
    fake_lookup.lookup.return_value = "Some Vendor Inc"

    with patch("oui_lookup.MacLookup", return_value=fake_lookup):
        result = oui_lookup.get_vendor("aa:bb:cc:dd:ee:ff")

    assert result == "Some Vendor Inc"


def test_get_vendor_returns_none_when_not_found():
    oui_lookup._lookup = None
    fake_lookup = MagicMock()
    fake_lookup.lookup.side_effect = VendorNotFoundError("nope")

    with patch("oui_lookup.MacLookup", return_value=fake_lookup):
        result = oui_lookup.get_vendor("00:00:00:00:00:00")

    assert result is None
