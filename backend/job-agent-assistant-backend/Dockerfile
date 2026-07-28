FROM python:3.12-slim

ARG APT_MIRROR="mirrors.aliyun.com"
ARG PIP_MIRROR="https://mirrors.aliyun.com/pypi/simple/"

RUN if [ -n "$APT_MIRROR" ]; then \
    sed -i "s|deb\.debian\.org|$APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources && \
    sed -i "s|security\.debian\.org|$APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources && \
    echo "=== APT mirror: $APT_MIRROR ==="; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice-writer \
        libpq-dev \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
        fonts-wqy-microhei \
        fonts-wqy-zenhei \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

RUN mkdir -p /app/logs /app/uploads/resumes /app/uploads/knowledge /app/models/huggingface /root/.EasyOCR/model \
    && chown -R appuser:appuser /app /root/.EasyOCR

COPY requirements.txt .
RUN if [ -n "$PIP_MIRROR" ]; then \
    pip install --no-cache-dir -i "$PIP_MIRROR" --trusted-host "${PIP_MIRROR#https://}" -r requirements.txt; \
    else \
    pip install --no-cache-dir -r requirements.txt; \
    fi

COPY --chown=appuser:appuser . .

RUN chmod +x docker-entrypoint.sh

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
