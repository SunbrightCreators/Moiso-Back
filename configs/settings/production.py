from .base import *

# 배포 환경용 env 파일 읽기
environ.Env.read_env(os.path.join(BASE_DIR, "env", ".env.production"))

DEBUG = False

DATABASES = {
    'default': env.db(),
}

CACHES = {
    'default': env.cache(),
}

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

CORS_ORIGIN_ALLOW_ALL = True
