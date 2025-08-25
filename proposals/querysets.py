from django.db import models
from django.db.models import  Count, OuterRef, Exists, BooleanField, Case, When, Value, F, Max, Q
from utils.choices import IndustryChoices
from fundings.models import Funding
from functools import reduce
from operator import or_

class ProposalQuerySet(models.QuerySet):
    def with_user(self):
        return self.select_related(
            'user__user',
        )

    def with_analytics(self):
        return (
            self.annotate(
                # distinct=True: 여러 관계를 한 쿼리에서 annotate할 때 join 곱셈으로 카운트가 부풀 수 있어요. likes에도 넣는 게 안전합니다.
                likes_count=Count('proposer_like_proposal', distinct=True),
                proposer_scraps=Count('proposer_scrap_proposal', distinct=True),
                founder_scraps=Count('founder_scrap_proposal', distinct=True),
        )
        .annotate(scraps_count=F('proposer_scraps') + F('founder_scraps'))
    )
    

    def filter_address(self, sido, sigungu, eupmyundong):
        if not (sido and sigungu and eupmyundong):
            return self

        return self.filter(
            address__sido=sido,
            address__sigungu=sigungu,
            address__eupmyundong=eupmyundong,
        )
    def filter_industry_choice(self, industry: str | None):
        """industry가 None이면 통과, 값이 있으면 유효성 검사 후 필터. 잘못된 값이면 ValueError."""
        if not industry:
            return self
        valid = {c for c, _ in IndustryChoices.choices}
        if industry not in valid:
            raise ValueError("Invalid industry choice.")
        return self.filter(industry=industry)

    def with_level_area(self, *, sido: str, sigungu: str, eupmyundong: str):
        """해당 동 기준 제안자 레벨(정렬용) 주입"""
        return self.annotate(
            level_area=Max(
                "user__proposer_level__level",
                filter=Q(
                    user__proposer_level__address__sido=sido,
                    user__proposer_level__address__sigungu=sigungu,
                    user__proposer_level__address__eupmyundong=eupmyundong,
                ),
            )
        )
    def order_by_choice(self, order: str):
        """
        정렬은 '인기순'/'최신순'/'레벨순'
        """
        if order not in ("인기순", "최신순", "레벨순"):
            raise ValueError("Invalid order. Use one of ['인기순','최신순','레벨순'].")
        order_map = {
            "인기순": "-likes_count",
            "최신순": "-created_at",
            "레벨순": "-level_area",
        }
        return self.order_by(order_map[order], "-id")
    
    def with_flags(self, *, user=None, profile: str = "", viewer_addr: dict | None = None):
        """
        리스트(동 이하) 카드용 플래그들:
        - is_liked: (proposer 전용)
        - is_scrapped: (proposer/founder)
        - is_address: 뷰어 주소(읍면동) == 제안글 주소(읍면동)
        """
        p = (profile or "").lower()

        # normalize viewer addresses
        addrs = []
        if isinstance(viewer_addr, dict):
            addrs = [viewer_addr]
        elif isinstance(viewer_addr, list):
            addrs = [a for a in viewer_addr if isinstance(a, dict)]

        # build OR(Q(...)) for multiple addresses
        if addrs:
            conds = [
                Q(
                    address__sido=a.get("sido"),
                    address__sigungu=a.get("sigungu"),
                    address__eupmyundong=a.get("eupmyundong"),
                )
                for a in addrs
            ]
            q_addr = reduce(or_, conds)
            is_address_expr = Case(When(q_addr, then=Value(True)),
                                default=Value(False),
                                output_field=BooleanField())
        else:
            is_address_expr = Value(False, output_field=BooleanField())

        if p == "proposer":
            like_expr = Exists(
                self.model._meta.apps.get_model("proposals", "ProposerLikeProposal")
                .objects.filter(proposal=OuterRef("pk"), user=user.proposer)
            )
            scrap_expr = Exists(
                self.model._meta.apps.get_model("proposals", "ProposerScrapProposal")
                .objects.filter(proposal=OuterRef("pk"), user=user.proposer)
            )
        elif p == "founder":
            like_expr = Value(False, output_field=BooleanField())
            scrap_expr = Exists(
                self.model._meta.apps.get_model("proposals", "FounderScrapProposal")
                .objects.filter(proposal=OuterRef("pk"), user=user.founder)
            )
        else:
            like_expr = Value(False, output_field=BooleanField())
            scrap_expr = Value(False, output_field=BooleanField())

        return self.annotate(
            is_liked=like_expr,
            is_scrapped=scrap_expr,
            is_address=is_address_expr,
        )
    
    def with_has_funding(self):
        return self.annotate(
            has_funding=Exists(Funding.objects.filter(proposal_id=OuterRef("pk")))
        )
