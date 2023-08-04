#!/bin/bash
set -eo pipefail
shopt -s nullglob

alembic upgrade head

exec python -m bot
