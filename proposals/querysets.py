from typing import Literal
from django.db import models
from django.db.models import Count, Q
from utils.choices import ProfileChoices

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
        if not (sido and sigungu and eupmyundong):
            return self

        return self.filter(
            address__sido=sido,
            address__sigungu=sigungu,
            address__eupmyundong=eupmyundong,
        )

    def filter_user_address(self, user, profile:Literal['proposer','founder']):
        user_profile = getattr(user, profile)
        if profile == ProfileChoices.proposer.value:
            address = user_profile.proposer_level.address
        elif profile == ProfileChoices.founder.value:
            address = user_profile.address

        return self.filter_address(
            sido=address['sido'],
            sigungu=address['sigungu'],
            eupmyundong=address['eupmyundong'],
        )

    def filter_user_industry(self, user, profile:Literal['proposer','founder']):
        user_profile = getattr(user, profile)
        industrys = user_profile.industry

        condition = Q()
        for industry in industrys:
            condition |= Q(industry=industry)

        return self.filter(condition)
