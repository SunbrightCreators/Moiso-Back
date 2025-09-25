from .base import *

DEBUG = False

DATABASES = {
    'default': env.db(),
}

CACHES = {
    'default': env.cache(),
}

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

CORS_ORIGIN_ALLOW_ALL = True

NCLOUD_CLIENT_ID = env('NCLOUD_CLIENT_ID')
NCLOUD_CLIENT_SECRET = env('NCLOUD_CLIENT_SECRET')
