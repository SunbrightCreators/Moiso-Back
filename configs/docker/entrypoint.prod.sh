#!/bin/sh
# python manage.py collectstatic --no-input echo "Apply database migrations" python manage.py migrate

set -e


# 1) 모델 존재 확인
: "${FT_MODEL_PATH:=/models/cc.ko.300.bin}"
if [ ! -f "$FT_MODEL_PATH" ]; then
  echo "❌ Model not found at $FT_MODEL_PATH"
  ls -l /models || true
  exit 1
fi

python manage.py collectstatic --no-input

python manage.py migrate
exec "$@"