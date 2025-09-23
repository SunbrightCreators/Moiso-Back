#!/usr/bin/env bash
set -euo pipefail

# settings 기본값을 production으로 강제
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-configs.settings.production}"

echo "[entrypoint] DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"

# 여기서 migrate/collectstatic 등을 실행한다면 반드시 이 env로 실행됨
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# gunicorn 실행 위임
exec "$@"
