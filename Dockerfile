# =====================================================================
# Automated Test Execution Platform — application server image
#
# This image runs the FastAPI app itself. It does NOT execute
# untrusted uploaded code directly - that happens in short-lived
# containers built from sandbox.Dockerfile, launched via the host
# Docker socket (see docker-compose.yml). This image only needs the
# `docker` CLI to talk to that socket.
# =====================================================================

FROM python:3.12-slim

LABEL maintainer="platform-team"
LABEL description="Automated Test Execution Platform - API server"

# Install the Docker CLI so the app can launch sandboxed execution
# containers via the mounted host Docker socket.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        gcc \
        default-jdk && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends docker-ce-cli && \
    apt-get purge -y --auto-remove gnupg lsb-release && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

RUN mkdir -p /app/backend/uploads/reports /app/backend/temp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
