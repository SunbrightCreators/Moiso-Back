from .base import *
import environ

environ.Env.read_env(os.path.join(BASE_DIR, 'env', '.env.development'))

DATABASES = {
    'default': env.db(),
}

CACHES = {
    'default': env.cache(),
}

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
