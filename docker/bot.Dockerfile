FROM python:3.11.4-slim-buster

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.5.1 \
    DISABLE_POETRY_CREATE_RUNTIME_FILE=1 \
    PYTHON_RUNTIME_VERSION=3.11.4

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && pip install "poetry==$POETRY_VERSION"

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY pyproject.toml poetry.lock* ./docker/bot-entrypoint.sh ./

RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

COPY src/ /usr/src/app/

ENTRYPOINT ["./bot-entrypoint.sh"]
