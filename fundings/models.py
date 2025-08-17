from django.conf import settings
from django.core.validators import RegexValidator, MaxLengthValidator
from django.db import models
from django.contrib.postgres.fields import ArrayField

from utils.choices import (
    RadiusChoices,
    BankCategoryChoices,
    FundingStatusChoices,
    RewardCategoryChoices,
    RewardAmountChoices,
)

yyyymm_validator = RegexValidator(
    regex=r"^\d{4}-(0[1-9]|1[0-2])$",
    message="YYYY-MM 형식으로 입력하세요!",
)


class Funding(models.Model):
    id = models.BigAutoField(
        primary_key=True
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fundings",
    )

    '''
    proposal = models.OneToOneField(
        "proposals.Proposal",
        on_delete=models.PROTECT,
        related_name="funding",
    )
    '''

    title = models.CharField(
        max_length=50,
    )

    summary = models.TextField(
        validators=[MaxLengthValidator(100)],
        blank=True,
    )

    content = models.TextField(
        validators=[MaxLengthValidator(1000)],
        blank=True,
    )

    business_hours = models.JSONField() # {  "start": "시작시간",  "end": "종료시간"}

    # 배열 선택 + size=3 (예: 반경 최대 3개 저장)
    radius = ArrayField(
        base_field=models.PositiveSmallIntegerField(
            choices=RadiusChoices.choices
        ),
        size=3,
    )

    contact = models.CharField(
        max_length=50,
        blank=True,
    )

    goal_amount = models.PositiveBigIntegerField()

    schedule = models.JSONField( # {  "start": "시작일",  "end": "종료일"}
        blank=True,
    )

    schedule_description = models.TextField(
        validators=[MaxLengthValidator(1000)],
        blank=True,
    )

    expected_opening_date = models.CharField(
        max_length=7,
        validators=[yyyymm_validator],
    )

    amount_description = models.TextField(
        validators=[MaxLengthValidator(1000)],
    )

    founder_name = models.CharField(
        max_length=30,
    )

    founder_description = models.TextField(
        validators=[MaxLengthValidator(500)],
    )

    founder_image = models.ImageField(
        upload_to="fundings/founder/",
    )

    bank_category = ArrayField(
        base_field=models.CharField(
            max_length=10,
            choices=BankCategoryChoices.choices,
        ),
        size=2,
    )

    bank_account = models.CharField(
        max_length=16,
    )

    bank_bankbook = models.FileField(
        upload_to="fundings/bankbook/",
    )

    policy = models.TextField(
        validators=[MaxLengthValidator(500)],
    )

    expected_problem = models.TextField(
        validators=[MaxLengthValidator(500)],
    )

    status = models.CharField(
        max_length=11,
        choices=FundingStatusChoices.choices,
    )

    reward_code = models.CharField(
        max_length=4,
    )

    def __str__(self):
        return f"[{self.id}] {self.title}"


class FundingImage(models.Model):
    funding = models.ForeignKey(
        Funding,
        on_delete=models.CASCADE,
        related_name="images",
    )

    image = models.ImageField(
        upload_to="fundings/images/",
    )

    def __str__(self):
        return f"FundingImage({self.funding_id})"


class FundingVideo(models.Model):
    funding = models.ForeignKey(
        Funding,
        on_delete=models.CASCADE,
        related_name="videos",
    )

    file = models.FileField(
        upload_to="fundings/videos/",
        blank=True,
    )

    def __str__(self):
        return f"FundingVideo({self.funding_id})"


class Reward(models.Model):
    id = models.BigAutoField(
        primary_key=True
    )

    # 리워드는 펀딩과 분리 생성될 수 있다고 가정(레벨 리워드) → nullable 허용
    funding = models.ForeignKey(
        Funding,
        on_delete=models.CASCADE,
        related_name="rewards",
        null=True,
        blank=True,
    )

    category = models.CharField(
        max_length=6,
        choices=RewardCategoryChoices.choices,
    )

    title = models.CharField(
        max_length=30,
    )

    content = models.TextField(
        validators=[MaxLengthValidator(50)],
    )

    amount = models.PositiveSmallIntegerField(
        choices=RewardAmountChoices.choices,
    )

    expired_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"[{self.id}] {self.title}"
