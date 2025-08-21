from django.db import models
from django.db.models import Q, Count, Sum
from utils.choices import PaymentStatusChoices

class FundingManager(models.Manager):
    def with_proposal(self):
        return self.select_related(
            'proposal',
        )

    def with_analytics(self):
        return self.annotate(
            likes_count=Count('proposer_like_funding'),
            scraps_count=Count('proposer_scrap_funding')+Count('founder_scrap_funding'),
            amount=Sum(
                'payment__total_amount',
                filter=Q(payment__status=PaymentStatusChoices.DONE),
            ),
        )

    def filter_address(self, sido, sigungu, eupmyundong):
        return self.filter(
            proposal__address__sido=sido,
            proposal__address__sigungu=sigungu,
            proposal__address__eupmyundong=eupmyundong,
        )
