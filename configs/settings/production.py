from .base import *
import environ

environ.Env.read_env(os.path.join(BASE_DIR, 'env', '.env.production'))

DATABASES = {
    'default': env.db(),
}

CACHES = {
    'default': env.cache(),
}

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

CORS_ORIGIN_ALLOW_ALL = True
