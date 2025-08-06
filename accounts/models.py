from string import ascii_lowercase, digits
from django.contrib.auth.models import AbstractUser
from django.db import models
from django_nanoid.models import NANOIDField
from .managers import UserManager
from utils.choices import GenderChoices

class User(AbstractUser):
    # AbstractUser 모델 오버라이딩
    username = None
    gender = models.CharField(max_length=1, choices=GenderChoices.choices, default = "F")
    birth_year=models.IntegerField(default=1990)
    email = models.EmailField(
        unique=True,
        error_messages={
            'unique': '이미 존재하는 이메일입니다.',
            'invalid': '잘못된 이메일 형식입니다.',
            },
    )
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    # 커스텀 필드
    id = NANOIDField(
        primary_key=True,
        verbose_name='ID',
        editable=False,
        secure_generated=True,
        alphabetically=ascii_lowercase+digits,
        size=21,
    )

    def __str__(self):
        return self.email
