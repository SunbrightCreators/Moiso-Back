from string import ascii_lowercase, digits

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from django_nanoid.models import NANOIDField
from django.contrib.postgres.fields import ArrayField

from .managers import UserManager
from utils.choices import *

class User(AbstractUser):
    # AbstractUser 모델 오버라이딩
    username = None
    first_name = None
    last_name = None

    email = models.EmailField(
        unique=True,
        error_messages={
            'unique': '이미 존재하는 이메일입니다.',
        },
    )

    # 커스텀 필드
    id = NANOIDField(
        primary_key=True,
        verbose_name='ID',
        editable=False,
        secure_generated=True,
        alphabetically=ascii_lowercase + digits,
        size=21,
    )

    # 권한/상태
    is_staff = models.BooleanField(
        default=False,
    )
    is_active = models.BooleanField(
        default=True,
    )
    date_joined = models.DateTimeField(
        default=timezone.now,
    )

    is_marketing_allowed = models.BooleanField(
        default=False
    )  # 마케팅 및 메시지 수신 동의
    name = models.CharField(
        max_length=10,
    )  # 이름(실명)

    birth = models.CharField(
        max_length=6,
    )  # 생년월일 (YYMMDD 등 고정 6자리 표기)

    sex = models.CharField(
        max_length=5,
        choices=SexChoices.choices,
    )  # 성별

    profile_image = models.ImageField(
        upload_to='user',
        null=True,
        blank=True,
    )

    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class Proposer(models.Model):
    id = NANOIDField(
        primary_key=True,
        size=21,  
        unique=True,
        editable=False,
        secure_generated=True,
        alphabetically=ascii_lowercase + digits,
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    industry = ArrayField(
        base_field=models.CharField(
            max_length=24,
            choices=IndustryChoices.choices,
        ),
        size=3,
    )

class Founder(models.Model):
    id = NANOIDField(
        primary_key=True,
        size=21,  
        unique=True,
        editable=False,
        secure_generated=True,
        alphabetically=ascii_lowercase + digits,
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    industry = ArrayField(
        base_field=models.CharField(
            max_length=24,
            choices=IndustryChoices.choices,
        ),
        size=3,
    )
    address = models.JSONField()   # { sido, sigungu, eupmyundong }
    target = ArrayField(
        base_field=models.CharField(
            max_length=8,
            choices=FounderTargetChoices.choices,
        ),
        size=2,
    )
    business_hours = models.JSONField()  # { start, end }

class LocationHistory(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )

    user = models.ForeignKey(
        "Proposer",
        on_delete=models.CASCADE,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    address = models.JSONField()  # { sido, sigungu, eupmyundong }

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'user', 
                    'created_at'
                    ],
                name='unique_user_created_at',
            )   
       ]


class ProposerLevel(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )

    user = models.ForeignKey(
        "Proposer",
        on_delete=models.CASCADE,
    )

    address = models.JSONField()  # { sido, sigungu, eupmyundong }

    level = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(3),
        ],
    )


class PushSubscription(models.Model):
    id = models.BigAutoField(
        primary_key=True,
    )

    user = models.ForeignKey(
        "Proposer",
        on_delete=models.CASCADE,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    endpoint = models.URLField(
        max_length=500,
    )

    p256dh_key = models.CharField(
        max_length=100,
    )

    auth_key = models.CharField(
        max_length=50,
    )

    is_main = models.BooleanField()

    is_active = models.BooleanField(
        default=True,
    )

    last_success = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'user', 
                    'endpoint'
                ],
                name='unique_user_endpoint',
            )
       ]

