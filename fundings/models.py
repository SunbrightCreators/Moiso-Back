from string import ascii_lowercase, digits
from django_nanoid.models import NANOIDField
from django.core.validators import RegexValidator
from django.db import models
from utils.choices import (
    RadiusChoices,
    BankCategoryChoices,
    FundingStatusChoices,
    RewardCategoryChoices,
    RewardAmountChoices,
    RewardStatusChoices,
)

class Funding(models.Model):
    user = models.ForeignKey(
        "accounts.Founder",
        on_delete=models.CASCADE,
        related_name="funding",
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
    summary = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    content = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
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
    radius = models.PositiveSmallIntegerField(
        choices=RadiusChoices.choices,
    )
    image1 = models.ImageField(
        upload_to='funding/image',
    )
    image2 = models.ImageField(
        upload_to='funding/image',
        null=True,
        blank=True,
    )
    image3 = models.ImageField(
        upload_to='funding/image',
        null=True,
        blank=True,
    )
    video = models.FileField(
        upload_to='funding/video',
        null=True,
        blank=True,
    )
    contact = models.CharField(
        max_length=50,
    )
    goal_amount = models.PositiveBigIntegerField()
    schedule = models.JSONField(
        default=dict,
        help_text='''
        {
            "start": "2025-07-21",
            "end": "2025-08-24",
        }
        '''
    )
    schedule_description = models.CharField(
       max_length=1000,
    )
    expected_opening_date = models.CharField(
        max_length=7,
        validators=[
            RegexValidator(
                regex=r"^\d{4}-(0[1-9]|1[0-2])$",
                message="YYYY-MM 형식으로 입력하세요!",
            )
        ],
    )
    amount_description = models.CharField(
        max_length=1000,
    )
    founder_name = models.CharField(
        max_length=30,
    )
    founder_description = models.CharField(
        max_length=500,
    )
    founder_image = models.ImageField(
        upload_to="funding/founder_image",
    )
    bank_category = models.CharField(
        max_length=10,
        choices=BankCategoryChoices.choices,
    )
    bank_account = models.CharField(
        max_length=16,
    )
    bank_bankbook = models.FileField(
        upload_to="funding/bank_bankbook",
    )
    policy = models.CharField(
        max_length=500,
    )
    expected_problem = models.CharField(
        max_length=500,
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

class Reward(models.Model):
    # 리워드는 펀딩과 분리 생성될 수 있다고 가정(레벨 리워드) → nullable 허용
    funding = models.ForeignKey(
        'Funding',
        on_delete=models.CASCADE,
        related_name="reward",
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
    content = models.CharField(
         max_length=50,
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

class ProposerReward(models.Model):
    id = NANOIDField(
        primary_key=True,
        editable=False,
        secure_generated=True,
        alphabetically=ascii_lowercase + digits,
        size=21,
    )
    user = models.ForeignKey(
        "accounts.Proposer",
        on_delete=models.CASCADE,
        related_name="proposer_reward",
    )
    reward = models.ForeignKey(
        "Reward",
        on_delete=models.CASCADE,
        related_name="proposer_reward",
    )
    status = models.CharField(
        max_length=7,
        choices=RewardStatusChoices.choices,
    )

    def __str__(self):
        return f"ProposerReward(proposer={self.user.id}, reward={self.reward.id})"

class FounderScrapFunding(models.Model):
    user = models.ForeignKey(
        "accounts.Founder",
        on_delete=models.CASCADE,
        related_name="founder_scrap_funding",
    )
    funding = models.ForeignKey(
        "Funding",
        on_delete=models.CASCADE,
        related_name="founder_scrap_funding",
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "funding"],
                name="unique_founder_scrap_funding",
            )
        ]

    def __str__(self):
        return f"FounderScrapFunding(founder={self.user.id}, funding={self.funding.id})"

class ProposerLikeFunding(models.Model):
    user = models.ForeignKey(
        "accounts.Proposer",
        on_delete=models.CASCADE,
        related_name="proposer_like_funding",
    )
    funding = models.ForeignKey(
        "Funding",
        on_delete=models.CASCADE,
        related_name="proposer_like_funding",
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "funding"],
                name="unique_proposer_like_funding",
            )
        ]

    def __str__(self):
        return f"ProposerLikeFunding(proposer={self.user.id}, funding={self.funding.id})"

class ProposerScrapFunding(models.Model):
    user = models.ForeignKey(
        "accounts.Proposer",
        on_delete=models.CASCADE,
        related_name="proposer_scrap_funding",
    )
    funding = models.ForeignKey(
        "Funding",
        on_delete=models.CASCADE,
        related_name="proposer_scrap_funding",
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "funding"],
                name="unique_proposer_scrap_funding",
            )
        ]

    def __str__(self):
        return f"ProposerScrapFunding(proposer={self.user.id}, funding={self.funding.id})"
