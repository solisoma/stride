FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
RUN set -eux; \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources; \
    apt-get -o Acquire::Retries=3 -o Acquire::https::Timeout=30 -o APT::Update::Error-Mode=any update; \
    apt-get -o Acquire::Retries=3 -o Acquire::https::Timeout=30 install -y --no-install-recommends ffmpeg; \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
ARG INSTALL_LOCAL_WHISPER=false
RUN if [ "$INSTALL_LOCAL_WHISPER" = "true" ]; then uv sync --frozen --no-dev --extra media --extra postgres --extra local-whisper; else uv sync --frozen --no-dev --extra media --extra postgres; fi
COPY . .
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001"]
