# Home Assistant with the LOCAL idm-heatpump-api pre-installed.
#
# The official HA image installs custom-integration requirements from PyPI at
# startup (homeassistant.util.package). To guarantee we test the CURRENT LOCAL
# API (not an older/cached published build), we force-install the locally
# built wheel into the HA Python environment. HA's requirement check then sees
# `idm-heatpump-api[web]==<local version>` as already satisfied and will NOT
# fetch PyPI.
#
# The image is pinned to the minimum Home Assistant version the integration's
# manifest supports, so bench results stay reproducible and never drift with
# `:stable`. Bump it together with the manifest minimum.
#
# The integration itself is mounted read-only at runtime via docker-compose
# (../custom_components/idm_heatpump -> /config/custom_components/idm_heatpump),
# so container rebuilds are not needed for integration code changes.

FROM ghcr.io/home-assistant/home-assistant:2026.11.0

ARG API_WHEEL

# The local API wheel plus the integration's validated transport pair
# (modbus-connection/tmodbus — the integration injects these instead of the
# API's optional built-in pymodbus transport, so pymodbus is NOT installed
# here). Installing them explicitly satisfies the integration's manifest
# requirements and keeps HA's startup check from fetching PyPI. aiohttp for
# the [web] extra already ships with Home Assistant.
COPY wheels/${API_WHEEL} /tmp/${API_WHEEL}
RUN pip install --no-cache-dir --force-reinstall \
        "/tmp/${API_WHEEL}[web]" \
        "modbus-connection>=4.12.7" \
        "tmodbus[async-serial]>=0.6.2" \
    && rm -f /tmp/${API_WHEEL} \
    && python -c "import idm_heatpump; print('idm-heatpump-api', __import__('importlib.metadata').metadata.version('idm-heatpump-api'))" \
    && python -c "import modbus_connection, tmodbus; print('transport pair ready')"

# Healthcheck is configured in docker-compose (TCP check against the API port).
