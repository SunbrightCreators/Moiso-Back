from django.db import models
from utils.choices import IndustryChoices, RadiusChoices

class Proposal(models.Model):
    user = models.ForeignKey(
        'accounts.Proposer',
        on_delete=models.CASCADE,
        related_name='proposal',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )
    title = models.CharField(
        max_length=50,
    )
    content = models.TextField(
        max_length=1000,
    )
    industry = models.CharField(
        max_length=24,
        choices=IndustryChoices.choices,
    )
    business_hours = models.JSONField(
        default=dict,
        help_text='''
        {
            'start': '09:00',
            'end': '18:00',
        }
        '''
    )
    address = models.JSONField(
        default=dict,
        help_text='''
        {
            'sido': '전라남도',
            'sigungu': '광양시',
            'eupmyundong': '광양읍',
            'jibun_detail': '읍내리 252-1',
            'road_detail': '매일시장길 20'
        }
        '''
    )
    position = models.JSONField(
        default=dict,
        help_text='''
        {
            "latitude": 126.978388,
            "longitude": 37.56661
        }
        '''
    )
    radius = models.PositiveSmallIntegerField(
        choices=RadiusChoices.choices,
    )
    image1 = models.ImageField(
        upload_to='proposal/image',
        null=True,
        blank=True,
    )
    image2 = models.ImageField(
        upload_to='proposal/image',
        null=True,
        blank=True,
    )
    image3 = models.ImageField(
        upload_to='proposal/image',
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.title

class ProposerLikeProposal(models.Model):
    user = models.ForeignKey(
        'accounts.Proposer',
        on_delete=models.CASCADE,
        related_name='proposer_like_proposal',
    )
    proposal = models.ForeignKey(
        'Proposal',
        on_delete=models.CASCADE,
        related_name='proposer_like_proposal',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f'{self.user.user.email} 님이 {self.proposal.title} 제안글을 좋아해요.'

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user','proposal'],
                name='unique_user_proposal',
                violation_error_message='제안자는 제안글을 한 번만 좋아요할 수 있어요.',
            )
        ]
