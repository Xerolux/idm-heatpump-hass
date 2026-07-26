# API tester: imports the EXACT local idm-heatpump-api code under test.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

ARG API_WHEEL=idm_heatpump_api-0.8.7-py3-none-any.whl

# Build deps for any wheel that needs them, then install the local API wheel
# (with [web] extra => aiohttp; pymodbus is a hard dep). The wheel is copied
# into the build context by scripts/build.ps1.
COPY wheels/${API_WHEEL:-idm_heatpump_api-0.8.7-py3-none-any.whl} /tmp/${API_WHEEL:-idm_heatpump_api-0.8.7-py3-none-any.whl}
RUN pip install --no-cache-dir "/tmp/${API_WHEEL:-idm_heatpump_api-0.8.7-py3-none-any.whl}[web]" \
    && rm -f "/tmp/${API_WHEEL:-idm_heatpump_api-0.8.7-py3-none-any.whl}" \
    && python -c "import idm_heatpump; import aiohttp; import pymodbus; print('api+web ready')"

COPY run_api_tests.py /app/run_api_tests.py
COPY ha_probe.py /app/ha_probe.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN id -u tester 2>/dev/null || useradd --create-home --uid 1000 tester \
    && mkdir -p /results \
    && chown -R tester:tester /app /results
USER tester

ENTRYPOINT ["/app/entrypoint.sh"]
