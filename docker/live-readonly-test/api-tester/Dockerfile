# API tester: imports the EXACT local idm-heatpump-api code under test.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

ARG API_WHEEL

# The local API wheel with both extras the isolated probes need:
#   [web]      — aiohttp for the Navigator web clients,
#   [pymodbus] — the API's optional built-in Modbus transport, used by the
#                isolated probes when no custom transport is injected. This is
#                NOT the integration's runtime path (HA injects
#                modbus-connection/tmodbus); it only serves this test container.
# The wheel is copied into the build context by scripts/build.ps1.
COPY wheels/${API_WHEEL} /tmp/${API_WHEEL}
RUN pip install --no-cache-dir "/tmp/${API_WHEEL}[web,pymodbus]" \
    && rm -f /tmp/${API_WHEEL} \
    && python -c "import idm_heatpump, aiohttp, pymodbus; print('api+web+probe-transport ready')"

COPY run_api_tests.py /app/run_api_tests.py
COPY ha_probe.py /app/ha_probe.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN id -u tester 2>/dev/null || useradd --create-home --uid 1000 tester \
    && mkdir -p /results \
    && chown -R tester:tester /app /results
USER tester

ENTRYPOINT ["/app/entrypoint.sh"]
