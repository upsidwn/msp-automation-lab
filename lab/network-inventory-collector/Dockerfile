# Container image for the collector. Mirrors the real project layout
# (source/, output/, known_good_firmware.json all siblings under /app)
# so the scripts' own relative path logic works unchanged, same as
# running them directly on a normal checkout.

FROM python:3.11-slim

# nmap: active scan (plain TCP connect mode, no elevated privileges
# needed). arp-scan: ARP sweep, needs NET_RAW/NET_ADMIN capabilities at
# `docker run` time to work unprivileged, see README for the flag.
# graphviz: the `dot` binary the device diagram shells out to.
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    arp-scan \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# Runs as a non-root user by default (least privilege). arp-scan still
# works unprivileged as this user as long as the container itself was
# started with --cap-add=NET_RAW --cap-add=NET_ADMIN.
RUN useradd --create-home --shell /bin/bash collector
WORKDIR /app

COPY source/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY source/ ./source/
COPY known_good_firmware.json .
RUN mkdir -p output && chown -R collector:collector /app

USER collector

ENTRYPOINT ["python", "source/menu.py"]
