# Read-only HTTP reverse proxy for the IDM Navigator 2.0 web interface.
FROM python:3.13-slim

LABEL org.opencontainers.image.title="idm-web-readonly-proxy"
LABEL org.opencontainers.image.description="Read-only HTTP reverse proxy (GET/HEAD + login POST only) for IDM live testing"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY web_proxy.py /app/web_proxy.py
COPY nav10_ws_proxy.py /app/nav10_ws_proxy.py
COPY start_web_proxy.py /app/start_web_proxy.py

RUN id -u proxy 2>/dev/null || useradd --create-home --uid 1000 proxy
USER proxy

EXPOSE 80 61220
CMD ["python", "-u", "/app/start_web_proxy.py"]
