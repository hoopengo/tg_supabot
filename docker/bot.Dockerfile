ARG PYTHON_VERSION=3.14.3-slim-trixie
FROM python:${PYTHON_VERSION} AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/uv
ENV PATH="/uv/bin:$PATH"

WORKDIR /usr/src/app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src/ /usr/src/app/src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:${PYTHON_VERSION}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

COPY --from=builder /usr/src/app/.venv .venv
COPY --from=builder /usr/src/app/src/ src/
COPY docker/bot-entrypoint.sh ./
RUN chmod +x bot-entrypoint.sh

ENV PATH="/usr/src/app/.venv/bin:$PATH"

ENTRYPOINT ["./bot-entrypoint.sh"]
