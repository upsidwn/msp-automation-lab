# Redraws a one-line-per-IP progress table in place as discover.py's
# three passes (nmap dispatch, mDNS, ARP) find or confirm things, instead
# of scrolling a new line every time the same IP gets more info. Falls
# back to plain sequential printing when stdout isn't a real terminal
# (piped, redirected, captured by a test), since moving the cursor only
# makes sense on an actual screen.
#
# Confirmed live: a row with enough services/hostname/vendor text piled
# on eventually gets longer than the terminal is wide, and the terminal
# wraps it onto two physical lines. The redraw math moves the cursor up
# by a count of logical rows, so once one row silently occupies two
# screen lines, that count stops matching reality and later redraws
# land on the wrong line, overwriting the middle of the table instead
# of the top. Every row gets truncated to the terminal width now so one
# row is always exactly one physical line, no exceptions.

import shutil
import sys


def _truncate(text, width):
    if width <= 0 or len(text) <= width:
        return text
    if width <= 3:
        return text[:width]

    return text[: width - 3] + "..."


def _format_row(info):
    fields = []
    for key in ("status", "vendor", "model", "hostname", "mac", "mac_vendor"):
        value = info.get(key)
        if value:
            fields.append(value)

    if info.get("services"):
        fields.append(", ".join(info["services"]))

    if not fields:
        return info["ip"]

    return f"{info['ip']} - {', '.join(fields)}"


class LiveTable:
    def __init__(self, stream=None):
        self._stream = stream or sys.stdout
        self._rows = {}
        self._order = []
        self._drawn_lines = 0

    def upsert(self, ip, **fields):
        """Adds a new row for ip, or merges fields into its existing row
        if it's already been seen. Omitting a field (or passing None)
        leaves whatever was already there alone, so a later pass that
        doesn't know a field (e.g. ARP has no hostname) never blanks out
        what an earlier pass already found. Passing an empty string
        explicitly clears a field, used to drop a "scanning..." status
        once a device turns out to be identified.
        """
        if ip not in self._rows:
            self._rows[ip] = {"ip": ip}
            self._order.append(ip)

        for key, value in fields.items():
            if value is not None:
                self._rows[ip][key] = value

        self._redraw(ip)

    def _redraw(self, changed_ip):
        if self._stream.isatty():
            self._redraw_in_place()
        else:
            self._stream.write(_format_row(self._rows[changed_ip]) + "\n")

    def _redraw_in_place(self):
        width = shutil.get_terminal_size(fallback=(80, 24)).columns

        if self._drawn_lines:
            self._stream.write(f"\033[{self._drawn_lines}A")
        for ip in self._order:
            line = _truncate(_format_row(self._rows[ip]), width)
            self._stream.write("\033[2K" + line + "\n")
        self._drawn_lines = len(self._order)
