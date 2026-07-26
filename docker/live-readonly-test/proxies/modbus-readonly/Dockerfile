# Read-only Modbus TCP proxy. Pure Python stdlib (asyncio), no dependencies,
# so the function-code filter cannot be bypassed by a library upgrade.
FROM python:3.13-slim

LABEL org.opencontainers.image.title="idm-modbus-readonly-proxy"
LABEL org.opencontainers.image.description="Read-only Modbus TCP proxy (FC01-04 only) for IDM live testing"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

WORKDIR /app
COPY modbus_proxy.py /app/modbus_proxy.py

# Run as non-root.
RUN id -u proxy 2>/dev/null || useradd --create-home --uid 1000 proxy
USER proxy

EXPOSE 5020 5021
CMD ["python", "-u", "/app/modbus_proxy.py"]
