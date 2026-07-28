# Container image for the collector. Mirrors the real project layout
# (source/, output/, known_good_firmware.json all siblings under /app)
# so the scripts' own relative path logic works unchanged, same as
# running them directly on a normal checkout.

FROM python:3.11-slim

# nmap: active scan (plain TCP connect mode, no elevated privileges
# needed). arp-scan: ARP sweep. graphviz: the `dot` binary the device
# diagram shells out to. net-tools: provides the classic `arp` command
# (not arp-scan), which arp_lookup.py shells out to for reading the OS
# ARP cache. Confirmed live: python's slim base image doesn't include
# it, and its absence crashed the whole scan instead of just skipping
# the MAC lookup, see arp_lookup.py's fix. libcap2-bin: provides setcap,
# see below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    arp-scan \
    graphviz \
    net-tools \
    libcap2-bin \
    && rm -rf /var/lib/apt/lists/*

# Confirmed live: --cap-add=NET_RAW/NET_ADMIN at `docker run` only makes
# those capabilities available to the container, a non-root process
# doesn't get them automatically just by running inside it (unlike this
# dev machine's BPF group-permission model on macOS, a different
# mechanism entirely). Granting the capability directly to the arp-scan
# binary here means any user who runs it gets it, root or not, no sudo
# needed inside the container at all.
RUN setcap cap_net_raw,cap_net_admin+eip "$(command -v arp-scan)"

RUN useradd --create-home --shell /bin/bash collector
WORKDIR /app

COPY source/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY source/ ./source/
COPY known_good_firmware.json .
RUN mkdir -p output && chown -R collector:collector /app

USER collector

ENTRYPOINT ["python", "source/menu.py"]
