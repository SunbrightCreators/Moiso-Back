from django.db import models
from django.db.models import Count

class ProposalQuerySet(models.QuerySet):
    def with_user(self):
        return self.select_related(
            'user__user',
        )

    def with_analytics(self):
        return self.annotate(
            likes_count=Count('proposer_like_proposal'),
            scraps_count=Count('proposer_scrap_proposal')+Count('founder_scrap_proposal'),
        )

    def filter_address(self, sido, sigungu, eupmyundong):
        return self.filter(
            address__sido=sido,
            address__sigungu=sigungu,
            address__eupmyundong=eupmyundong,
        )
