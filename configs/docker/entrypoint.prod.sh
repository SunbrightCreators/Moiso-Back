#!/bin/sh
# python manage.py collectstatic --no-input echo "Apply database migrations" python manage.py migrate
python manage.py collectstatic --no-input
python manage.py makemigrations
python manage.py migrate
exec "$@"