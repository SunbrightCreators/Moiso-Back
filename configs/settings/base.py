from pathlib import Path
import os
from datetime import timedelta
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# env

env = environ.Env(DEBUG=(bool, False))

ENV_PATH = os.path.join(BASE_DIR, '.env')
if os.path.exists(ENV_PATH):
    environ.Env.read_env(ENV_PATH)  # 로컬/개발에서만 파일이 있으면 읽음

try:
    SECRET_KEY = env("SECRET_KEY")
except Exception as e:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        f"""
🚨 SECRET_KEY가 설정되지 않았습니다!

- 현재 BASE_DIR = {BASE_DIR}
- 읽으려는 .env 파일 경로 = {ENV_PATH}
- .env 파일 존재 여부 = {os.path.exists(ENV_PATH)}

확인하세요:
1) {ENV_PATH} 파일이 실제로 존재하는지?
2) .env 안에 'SECRET_KEY=...' 줄이 있는지?
3) docker-compose.prod.yml 의 env_file: .env 이 올바르게 연결되었는지?
4) 컨테이너 안에서 'printenv SECRET_KEY' 해봤을 때 값이 나오는지?

원래 에러: {str(e)}
"""
    )
DEBUG = env('DEBUG')
NCLOUD_CLIENT_ID = env('NCLOUD_CLIENT_ID')
NCLOUD_CLIENT_SECRET = env('NCLOUD_CLIENT_SECRET')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'accounts.apps.AccountsConfig',
    'maps.apps.MapsConfig',
    'proposals.apps.ProposalsConfig',
    'fundings.apps.FundingsConfig',
    'recommendations.apps.RecommendationsConfig',
    'pays.apps.PaysConfig',
    'notifications.apps.NotificationsConfig',
    'django_crontab',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'configs.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'configs.wsgi.application'

AUTH_USER_MODEL = 'accounts.User'


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'ko-kr'

TIME_ZONE = 'Asia/Seoul'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = os.getenv("STATIC_ROOT", "/home/app/web/static")

# Media files

MEDIA_URL = '/media/'
MEDIA_ROOT  = os.getenv("MEDIA_ROOT",  "/home/app/web/media")


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# CORS

CORS_ALLOW_METHODS = (
    'GET',
    'POST',
    'PUT',
    'PATCH',
    'DELETE',
    'OPTIONS',
)

CORS_ALLOW_HEADERS = (
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
)

CORS_ALLOW_CREDENTIALS = True


# Django REST Framework

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
}


# djangorestframework-simplejwt

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,

    'AUTH_HEADER_TYPES': ('Bearer',),
    
    'TOKEN_USER_CLASS': AUTH_USER_MODEL,
}

CRONJOBS = [
    ('0 0 * * *',  'fundings.crons.settle_fundings_job'),  # 매일 자정(00:00)
    ('0 0 * * 1',  'accounts.crons.compute_levels_job'),    # 매주 월요일 자정(00:00)
]

CRONJOBS_TIMEZONE = 'Asia/Seoul'

# 로그 파일을 저장할 디렉토리 설정
LOG_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    # 로그 포맷 정의
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
        'cron_format': {
            'format': '[{asctime}] {levelname} - {name}: {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },

    # 로그 핸들러 정의 (어디에 저장할지)
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },

        # Cron 작업 전용 로그 파일
        'cron_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'cron.log'),
            'maxBytes': 1024*1024*5,  # 5MB
            'backupCount': 5,
            'formatter': 'cron_format',
        },

        # 일반 Django 로그 파일
        'django_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'django.log'),
            'maxBytes': 1024*1024*10,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },

        # 에러 전용 로그 파일
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'error.log'),
            'maxBytes': 1024*1024*5,  # 5MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },

    # 로거 정의 (어떤 모듈의 로그를 어느 핸들러로 보낼지)
    'loggers': {
        # Cron 작업 로거
        'myapp.tasks': {
            'handlers': ['cron_file', 'console', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },

        # Django 전체 로거
        'django': {
            'handlers': ['django_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },

        # 루트 로거
        '': {
            'handlers': ['console', 'django_file', 'error_file'],
            'level': 'INFO',
        },
    },
}

LOGGING["loggers"].update({
    "accounts.crons":  {"handlers": ["cron_file", "console"], "level": "INFO", "propagate": False},
    "accounts.tasks":  {"handlers": ["cron_file", "console"], "level": "INFO", "propagate": False},
    "fundings.crons":  {"handlers": ["cron_file", "console"], "level": "INFO", "propagate": False},
    "fundings.tasks":  {"handlers": ["cron_file", "console"], "level": "INFO", "propagate": False},
})
