from string import ascii_lowercase, digits
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django_nanoid.models import NANOIDField
from django.contrib.postgres.fields import ArrayField
from utils.choices import SexChoices, IndustryChoices, FounderTargetChoices
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
    id = NANOIDField(
        primary_key=True,
        verbose_name='ID',
        editable=False,
        secure_generated=True,
        alphabetically=ascii_lowercase + digits,
        size=21,
    )
    is_marketing_allowed = models.BooleanField(
        default=False,
        help_text='마케팅 및 메시지 수신 동의',
    )
    name = models.CharField(
        max_length=10,
        help_text='이름(실명)',
    )
    birth = models.CharField(
        max_length=6,
        help_text='생년월일 (YYMMDD 고정 6자리 표기)',
    )
    sex = models.CharField(
        max_length=5,
        choices=SexChoices.choices,
        help_text='성별',
    )
    profile_image = models.ImageField(
        upload_to='user/profile_image',
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.email

class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscription"
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
                fields=['user','endpoint'],
                name='unique_user_endpoint',
            )
       ]

class Proposer(models.Model):
    id = NANOIDField(
        primary_key=True,
        editable=False,
        secure_generated=True,
        alphabetically=ascii_lowercase + digits,
        size=21,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='proposer',
    )
    industry = ArrayField(
        base_field=models.CharField(
            max_length=24,
            choices=IndustryChoices.choices,
        ),
        size=3,
    )

class ProposerLevel(models.Model):

    user = models.ForeignKey(
        "Proposer",
        on_delete=models.CASCADE,
        related_name="proposer_level",
    )
    address = models.JSONField(
        default=dict,
    )
    level = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(3),
        ],
    )

class LocationHistory(models.Model):

    user = models.ForeignKey(
        "Proposer",
        on_delete=models.CASCADE,
        related_name="location_history",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    address = models.JSONField(
        default=dict,
        help_text='''
        {
            "sido": "전라남도",
            "sigungu": "광양시",
            "eupmyundong": "광양읍"
        }
        '''
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user','created_at'],
                name='unique_user_created_at',
            )
       ]

class Founder(models.Model):
    id = NANOIDField(
        primary_key=True,
        editable=False,
        secure_generated=True,
        alphabetically=ascii_lowercase + digits,
        size=21,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="founder",
    )
    industry = ArrayField(
        base_field=models.CharField(
            max_length=24,
            choices=IndustryChoices.choices,
        ),
        size=3,
    )
    address = ArrayField(
        base_field=models.JSONField(
            default=dict,
        ),
        size=2,
    )
    target = ArrayField(
        base_field=models.CharField(
            max_length=8,
            choices=FounderTargetChoices.choices,
        ),
        size=2,
    )
    business_hours = models.JSONField(
        default=dict,
        help_text='''
        {
            "start": "09:00",
            "end": "18:00",
        }
        '''
    )
