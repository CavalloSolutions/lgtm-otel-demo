FROM python:3.11-bullseye as build

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.6.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONPATH=/app

RUN pip install --upgrade pip && \
    pip --quiet --no-cache-dir install virtualenv && \
    pip --quiet --no-cache-dir install poetry==${POETRY_VERSION}

WORKDIR /app
COPY pyproject.toml poetry.lock ./

ARG VIRTUAL_ENV=/home/venv

RUN virtualenv ${VIRTUAL_ENV} && \
    poetry install --only main --no-interaction --no-ansi --no-root


COPY ./src/demo_api /demo_api

ENV PYTHONPATH=/home/venv/lib/python3.11/site-packages
ENV PATH="$PATH:/home/venv/bin"

EXPOSE 8080

WORKDIR /
ENTRYPOINT ["/home/venv/bin/python", "-u", "-m", "demo_api"]
