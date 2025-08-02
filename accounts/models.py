from string import ascii_lowercase, digits
from django.contrib.auth.models import AbstractUser
from django.db import models
from django_nanoid.models import NANOIDField
from .managers import UserManager

class User(AbstractUser):
    # AbstractUser 모델 오버라이딩
    username = None
    first_name = None
    last_name = None
    email = models.EmailField(
        unique=True,
        error_messages={'unique': '이미 존재하는 이메일입니다.',},
    )
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    # 커스텀 필드

    def __str__(self):
        return self.email
