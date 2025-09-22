#!/bin/sh
set -e

# DB 마이그레이션
python manage.py migrate --noinput

# 정적 파일 수집(반드시 비대화형)
python manage.py collectstatic --noinput

# 위가 성공하면 CMD 실행(gunicorn은 compose의 command에서 넘김)
exec "$@"
