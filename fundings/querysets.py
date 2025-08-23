from django.db import models
from django.db.models import Q, Count, Sum, OuterRef, Exists, BooleanField, Value, Max
from utils.choices import PaymentStatusChoices, IndustryChoices
from django.apps import apps as django_apps

class FundingQuerySet(models.QuerySet):
    def with_proposal(self):
        return self.select_related(
            'proposal','user'
        )

    def with_analytics(self):
        return self.annotate(
            likes_count=Count('proposer_like_funding', distinct=True),
            scraps_count=Count('proposer_scrap_funding', distinct=True)+Count('founder_scrap_funding', distinct=True),
            amount=Sum(
                'payment__total_amount',
                filter=Q(payment__status=PaymentStatusChoices.DONE),
            ),
        )

    def filter_address(self, sido, sigungu, eupmyundong):
        if not (sido and sigungu and eupmyundong):
            return self

        return self.filter(
            proposal__address__sido=sido,
            proposal__address__sigungu=sigungu,
            proposal__address__eupmyundong=eupmyundong,
        )
    
    # 업종 유효성 + 필터
    def filter_industry_choice(self, industry: str | None):
        if not industry:
            return self
        valid = {c for c, _ in IndustryChoices.choices}
        if industry not in valid:
            raise ValueError("Invalid industry choice.")
        return self.filter(proposal__industry=industry)

    # 레벨 정렬용 
    def with_level_area(self, *, sido: str, sigungu: str, eupmyundong: str):
        return self.annotate(
            level_area=Max(
                'proposal__user__proposer_level__level',
                filter=Q(
                    proposal__user__proposer_level__address__sido=sido,
                    proposal__user__proposer_level__address__sigungu=sigungu,
                    proposal__user__proposer_level__address__eupmyundong=eupmyundong,
                ),
            )
        )

    # 정렬 공통
    def order_by_choice(self, order: str):
        if order not in ("인기순", "최신순", "레벨순"):
            raise ValueError("Invalid order. Use one of ['인기순','최신순','레벨순'].")
        mapping = {
            "인기순": "-likes_count",
            "최신순": "-id",        # created_at 없으니 id로 최신 대용
            "레벨순": "-level_area",
        }
        return self.order_by(mapping[order], "-id")

    # is_liked / is_scrapped
    def with_flags(self, *, user=None, profile: str = ""):
        p = (profile or "").lower()
        get_model = django_apps.get_model

        if p == "proposer":
            like_expr = Exists(
                get_model("fundings", "ProposerLikeFunding").objects
                .filter(funding=OuterRef("pk"), user=user.proposer)
            )
            scrap_expr = Exists(
                get_model("fundings", "ProposerScrapFunding").objects
                .filter(funding=OuterRef("pk"), user=user.proposer)
            )
        elif p == "founder":
            like_expr = Value(False, output_field=BooleanField())
            scrap_expr = Exists(
                get_model("fundings", "FounderScrapFunding").objects
                .filter(funding=OuterRef("pk"), user=user.founder)
            )
        else:
            like_expr = Value(False, output_field=BooleanField())
            scrap_expr = Value(False, output_field=BooleanField())

        return self.annotate(is_liked=like_expr, is_scrapped=scrap_expr)
