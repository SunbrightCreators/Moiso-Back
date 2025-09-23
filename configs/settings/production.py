from .base import *

DATABASES = {
    'default': env.db(),
}

CACHES = {
    'default': env.cache(),
}

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

CORS_ORIGIN_ALLOW_ALL = True
