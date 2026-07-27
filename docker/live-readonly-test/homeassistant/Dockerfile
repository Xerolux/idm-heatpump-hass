# Home Assistant with the LOCAL idm-heatpump-api pre-installed.
#
# The official HA image installs custom-integration requirements from PyPI at
# startup (homeassistant.util.package). To guarantee we test the CURRENT LOCAL
# API (HEAD == v0.9.1 tag) and not an older/cached published build, we
# force-install the locally built wheel into the HA Python environment. HA's
# requirement check then sees `idm-heatpump-api[web]==0.9.1` as already
# satisfied and will NOT fetch PyPI.
#
# The integration itself is mounted read-only at runtime via docker-compose
# (../custom_components/idm_heatpump -> /config/custom_components/idm_heatpump),
# so container rebuilds are not needed for integration code changes.

FROM ghcr.io/home-assistant/home-assistant:stable

ARG API_WHEEL=idm_heatpump_api-0.9.1-py3-none-any.whl

# Verify the wheel is present in the build context, then install it (no-deps:
# pymodbus + aiohttp already ship with Home Assistant).
COPY wheels/${API_WHEEL} /tmp/${API_WHEEL}
RUN pip install --no-cache-dir --no-deps --force-reinstall /tmp/${API_WHEEL} \
    && rm -f /tmp/${API_WHEEL} \
    && python -c "import idm_heatpump; print('idm-heatpump-api', __import__('importlib.metadata').metadata.version('idm-heatpump-api'))"

# Home Assistant bundles pymodbus 3.11.x, but the integration requires
# >=3.12.1,<4.0 and HA's constrained pip resolver cannot upgrade it at runtime
# ("No solution found"). Pin it here so HA's requirement check is satisfied and
# it never tries to fetch from PyPI.
RUN pip install --no-cache-dir "pymodbus>=3.12.1,<4.0" \
    && python -c "import pymodbus; print('pymodbus', pymodbus.__version__)"

# Healthcheck is configured in docker-compose (curl against the API endpoint).
