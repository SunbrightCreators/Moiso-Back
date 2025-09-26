from .base import *

DEBUG = True

DATABASES = {
    'default': env.db(),
}


CACHES = {
    'default': env.cache(),
}

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])

NCLOUD_CLIENT_ID = env('NCLOUD_CLIENT_ID')
NCLOUD_CLIENT_SECRET = env('NCLOUD_CLIENT_SECRET')
