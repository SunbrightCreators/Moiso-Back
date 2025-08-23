from __future__ import annotations
from typing import List, Dict, Optional
from django.db.models import QuerySet, Count, Max
from datetime import datetime
from django.utils import timezone
from datetime import timedelta
from django.http import HttpRequest
from rest_framework.exceptions import PermissionDenied
from utils.choices import ProfileChoices, FundingStatusChoices, PaymentStatusChoices, IndustryChoices, RewardCategoryChoices
from utils.decorators import require_profile
from django.apps import apps as django_apps  
from django.core.exceptions import FieldError, ImproperlyConfigured
from .models import Funding, ProposerLikeFunding, ProposerScrapFunding, FounderScrapFunding, ProposerReward
from pays.models import Payment
from .serializers import (
    FundingListSerializer, 
    FundingDetailProposerSerializer, 
    FundingDetailFounderSerializer,
    FundingMyCreatedItemSerializer,
)

class ProposerLikeFundingService:
    def __init__(self, request:HttpRequest):
        self.request = request

    @require_profile(ProfileChoices.proposer)
    def post(self, funding_id:int) -> bool:
        '''
        Args:
            funding_id (int): 펀딩 id
        Returns:
            is_created (bool):
                - `True`: 좋아요 추가
                - `False`: 좋아요 삭제
        '''
        funding = Funding.objects.get(id=funding_id)
        if funding.user.user == self.request.user:
            raise PermissionDenied('자신의 펀딩을 좋아할 수 없어요.')

        obj, created = ProposerLikeFunding.objects.get_or_create(
            user=self.request.user.proposer,
            funding=funding,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

class ProposerScrapFundingService:
    def __init__(self, request:HttpRequest):
        self.request = request

    @require_profile(ProfileChoices.proposer)
    def post(self, funding_id:int) -> bool:
        '''
        Args:
            funding_id (int): 펀딩 id
        Returns:
            is_created (bool):
                - `True`: 스크랩 추가
                - `False`: 스크랩 삭제
        '''
        funding = Funding.objects.get(id=funding_id)
        if funding.user.user == self.request.user:
            raise PermissionDenied('자신의 펀딩을 스크랩할 수 없어요.')

        obj, created = ProposerScrapFunding.objects.get_or_create(
            user=self.request.user.proposer,
            funding=funding,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

    @require_profile(ProfileChoices.proposer)
    def get(self, sido:str|None=None, sigungu:str|None=None, eupmyundong:str|None=None):
        fundings = Funding.objects.filter(
            proposer_scrap_funding__user=self.request.user.proposer,
        ).filter_address(
            sido=sido,
            sigungu=sigungu,
            eupmyundong=eupmyundong,
        ).with_analytics(
        ).with_proposal(
        ).with_flags(
            user=self.request.user, 
            profile="proposer"
        ).order_by(
            '-proposer_scrap_funding__created_at',
        )
        serializer = FundingListSerializer(fundings, many=True, context={"request": self.request, "profile": "proposer"})
        return serializer.data

class FounderScrapFundingService:
    def __init__(self, request:HttpRequest):
        self.request = request

    @require_profile(ProfileChoices.founder)
    def post(self, funding_id:int) -> bool:
        '''
        Args:
            funding_id (int): 펀딩 id
        Returns:
            is_created (bool):
                - `True`: 스크랩 추가
                - `False`: 스크랩 삭제
        '''
        funding = Funding.objects.get(id=funding_id)
        if funding.user.user == self.request.user:
            raise PermissionDenied('자신의 펀딩을 스크랩할 수 없어요.')

        obj, created = FounderScrapFunding.objects.get_or_create(
            user=self.request.user.founder,
            funding=funding,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

    @require_profile(ProfileChoices.founder)
    def get(self, sido:str|None=None, sigungu:str|None=None, eupmyundong:str|None=None):
        fundings = Funding.objects.filter(
            founder_scrap_funding__user=self.request.user.founder,
        ).filter_address(
            sido=sido,
            sigungu=sigungu,
            eupmyundong=eupmyundong,
        ).with_analytics(
        ).with_proposal(
        ).with_flags(user=self.request.user, 
                     profile="founder"
        ).order_by(
            '-founder_scrap_funding__created_at',
        )
        serializer = FundingListSerializer(fundings, many=True, context={"request": self.request, "profile": "founder"})
        return serializer.data

class FundingMapService:
    """
    지도 조회용 집계 서비스
    뷰에서 GeocodingService로 좌표를 만든다.
    """

    def __init__(self, request: HttpRequest):
        self.request = request

    def _group_counts(self, base_qs, group: str, industry: Optional[str]) -> List[Dict]:
        base = base_qs.filter(status=FundingStatusChoices.IN_PROGRESS)
        if industry:
            valid = {c for c, _ in IndustryChoices.choices}
            if industry not in valid:
                base = base.none()
            else:
                base = base.filter(proposal__industry=industry)
        base = base.exclude(**{f"{group}__isnull": True}).exclude(**{group: ""})
        rows = base.values(group).annotate(number=Count("id")).order_by(group)
        return [{"address": r[group], "number": r["number"]} for r in rows]

    def cluster_counts_sido(self, industry: Optional[str]) -> List[Dict]:
        return self._group_counts(Funding.objects.all(), "proposal__address__sido", industry)

    def cluster_counts_sigungu(self, sido: str, industry: Optional[str]) -> List[Dict]:
        base = Funding.objects.filter(proposal__address__sido=sido)
        return self._group_counts(base, "proposal__address__sigungu", industry)

    def cluster_counts_eupmyundong(self, sido: str, sigungu: str, industry: Optional[str]) -> List[Dict]:
        base = Funding.objects.filter(
            proposal__address__sido=sido,
            proposal__address__sigungu=sigungu,
        )
        return self._group_counts(base, "proposal__address__eupmyundong", industry)


CANCELABLE_WINDOW = timedelta(days=7) # 승인 후 7일 내 취소 가능

# 노션 참고함
def build_my_payment_block(funding, user):
    if not user.is_authenticated:
        return None

    qs = Payment.objects.filter(
        funding_id=funding.id,
        user_id=user.id,
        status=PaymentStatusChoices.DONE,  # 상태: PaymentStatusChoices.DONE = 승인완료.
    )
    # 마지막 결제(승인) 시각
    last_payment = qs.order_by("-approved_at", "-pk").first()

    has_paid = last_payment is not None
    last_paid_at = None
    if last_payment and last_payment.approved_at:
        last_paid_at = timezone.localtime(last_payment.approved_at)

    # 간단 취소 가능 규칙: 승인 후 7일 내
    can_cancel = False
    if last_payment and last_payment.approved_at:
        can_cancel = (timezone.now() - last_payment.approved_at) <= CANCELABLE_WINDOW

    
    return {
        "has_paid": has_paid,
        "can_cancel": can_cancel,
        "last_paid_at": last_paid_at,
    }

# schedule 중 end 값만
def _schedule_end_dt(funding):
    try:
        return timezone.make_aware(datetime.strptime(funding.schedule["end"], "%Y-%m-%d"))
    except Exception:
        return None
    
# 노션 참고함
def build_actions_block(funding, user, my_payment):
    now = timezone.now()
    end_dt = _schedule_end_dt(funding)

    owner_user_id = getattr(getattr(funding, "user", None), "user_id", None)
    can_pay = (
        funding.status == FundingStatusChoices.IN_PROGRESS
        and end_dt is not None
        and end_dt >= now
        and owner_user_id != getattr(user, "id", None)
    )

    can_cancel_last_payment = False
    if my_payment and my_payment.get("last_paid_at"):
        can_cancel_last_payment = (timezone.now() - my_payment["last_paid_at"]) <= CANCELABLE_WINDOW
        
    return {"can_pay": can_pay, "can_cancel_last_payment": can_cancel_last_payment}

def _get_eupmyundong_from_proposer(proposer) -> str | None:
    """
    Proposer 객체에서 동(읍·면·동)을 최대한 안전하게 뽑아낸다.
    - accounts.Proposer.address 가 JSONField이며 {"eupmyundong": "..."} 구조라고 가정
    - 혹시 구조가 다를 수 있으므로 넓게 방어적으로 접근
    """
    # 1) proposer.address 가 dict 인 경우
    addr = getattr(proposer, "address", None)
    if isinstance(addr, dict):
        val = addr.get("eupmyundong")
        if val:
            return str(val)

    # 2) proposer.user 쪽에 있을 수도 있는 경우까지 방어 (필요하면 확장)
    user_obj = getattr(proposer, "user", None)
    if user_obj is not None:
        user_addr = getattr(user_obj, "address", None)
        if isinstance(user_addr, dict):
            val = user_addr.get("eupmyundong")
            if val:
                return str(val)

    return None

# 좋아요 산출
def build_likes_analysis(funding: Funding) -> dict:
    """
    좋아요 누른 proposer의 동(읍·면·동)과 펀딩 proposal의 동이
    같으면 local, 다르면 stranger 로 분류하여 비율 계산.
    - 가능하면 DB에서 직접 집계 (JSON key transform)
    - 모델 구조가 달라 에러가 나면 파이썬 폴백
    """
    # 펀딩의 기준 동(읍·면·동)
    proposal_addr = getattr(funding.proposal, "address", {}) or {}
    target_eup = proposal_addr.get("eupmyundong")
    # 기준 동이 없으면 모두 stranger 처리
    if not target_eup:
        total = ProposerLikeFunding.objects.filter(funding=funding).count()
        return {
            "local_count": 0,
            "stranger_count": total,
            "local_ratio": "0%",
        }


    try:
        total = ProposerLikeFunding.objects.filter(funding=funding).count()
        local = ProposerLikeFunding.objects.filter(
            funding=funding,
            user__address__eupmyundong=target_eup,
        ).count()

    except (FieldError, ImproperlyConfigured):

        likes = (
            ProposerLikeFunding.objects
            .filter(funding=funding)
            .select_related("user")  # accounts.Proposer
        )
        total = likes.count()
        local = 0
        local = sum(
            1 for lk in likes
            if _get_eupmyundong_from_proposer(lk.user) == target_eup
        )

    stranger = max(total - local, 0)
    ratio = f"{round((local / total) * 100)}%" if total else "0%"
    return {
        "local_count": local,
        "stranger_count": stranger,
        "local_ratio": ratio,
    }

class FundingDetailService:

    def __init__(self, request: HttpRequest):
        self.request = request

    def _get_funding(self, funding_id: int, profile: str) -> Funding:
        return (
            Funding.objects
            .with_analytics()
            .with_proposal()
            .with_flags(user=self.request.user, profile=profile)  # ← 추가
            .select_related("user", "proposal")
            .prefetch_related("reward")
            .get(id=funding_id)
        )

    def get(self, funding_id: int, profile: str) -> dict:
        funding = self._get_funding(funding_id, profile)
        profile = profile.lower()

        if profile == ProfileChoices.proposer.value:
            my_payment = build_my_payment_block(funding, self.request.user)
            ser = FundingDetailProposerSerializer(
                funding,
                context={
                    "request": self.request,
                    "profile": profile,           # ← 중요: profile 전달
                    "my_payment": my_payment,
                },
            )
            return ser.data

        if profile == ProfileChoices.founder.value:
            likes_analysis = build_likes_analysis(funding)
            ser = FundingDetailFounderSerializer(
                funding,
                context={
                    "request": self.request,
                    "profile": profile,           # ← 중요: profile 전달
                    "likes_analysis": likes_analysis,
                },
            )
            return ser.data

        raise PermissionDenied("허용되지 않은 profile 입니다. (founder|proposer)")
    

class FounderMyCreatedFundingService:
    def __init__(self, request: HttpRequest):
        self.request = request

    def _base_qs(self) -> QuerySet[Funding]:
        founder = getattr(self.request.user, "founder", None)
        if founder is None:
            raise PermissionDenied("창업자 프로필이 필요해요.")
        qs = Funding.objects.filter(user=founder).only("id", "title", "schedule", "status")
        return qs

    def _order_latest(self, qs: QuerySet[Funding]) -> QuerySet[Funding]:
        # 가능하면 제안글 생성일 기준 최신, 없으면 id 기반
        try:
            return qs.order_by("-proposal__created_at", "-id")
        except FieldError:
            return qs.order_by("-id")

    @require_profile(ProfileChoices.founder)
    def get(self) -> dict:
        qs = self._base_qs()

        in_progress_qs = self._order_latest(qs.filter(status=FundingStatusChoices.IN_PROGRESS))
        succeeded_qs   = self._order_latest(qs.filter(status=FundingStatusChoices.SUCCEEDED))
        failed_qs      = self._order_latest(qs.filter(status=FundingStatusChoices.FAILED))

        return {
            "in_progress": FundingMyCreatedItemSerializer(in_progress_qs, many=True).data,
            "succeeded":   FundingMyCreatedItemSerializer(succeeded_qs, many=True).data,
            "failed":      FundingMyCreatedItemSerializer(failed_qs, many=True).data,
        }
    
class ProposerMyPaidFundingService:
    def __init__(self, request: HttpRequest):
        self.request = request

    def _base_qs(self) -> QuerySet[Funding]:
        # 프로필 체크(방어)
        proposer = getattr(self.request.user, "proposer", None)
        if proposer is None:
            raise PermissionDenied("제안자 프로필이 필요해요.")

        # 내가 결제(DONE)한 펀딩들 + 마지막 결제시각 기준 최신순
        qs = (
            Funding.objects
            .filter(
                payment__user_id=self.request.user.id,
                payment__status=PaymentStatusChoices.DONE,
            )
            .annotate(last_paid_at=Max("payment__approved_at"))
            .only("id", "title", "schedule", "status")
            .order_by("-last_paid_at", "-id")
        )
        return qs
    
    @require_profile(ProfileChoices.proposer)
    def get(self) -> dict:
        qs = self._base_qs()
        return {
            "in_progress": FundingMyCreatedItemSerializer(
                qs.filter(status=FundingStatusChoices.IN_PROGRESS), many=True
            ).data,
            "succeeded": FundingMyCreatedItemSerializer(
                qs.filter(status=FundingStatusChoices.SUCCEEDED), many=True
            ).data,
            "failed": FundingMyCreatedItemSerializer(
                qs.filter(status=FundingStatusChoices.FAILED), many=True
            ).data,
        }
    
class ProposerMyRewardsService:
    def __init__(self, request: HttpRequest):
        self.request = request

    def _validate_and_norm_category(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        up = raw.upper()
        allowed = {"LEVEL", "GIFT", "COUPON"}
        if up not in allowed:
            raise ValueError(f"Invalid category. Use one of {sorted(allowed)}.")
        return up
    
    # 수정중! 종료된 펀딩의 '구매 리워드'를 cqy(수량)만큼 펼쳐서 dict 리스트로 반환
    def _purchased_reward_entries(self, cat: Optional[str]) -> list[dict]:
        """
        후원(Payment) 시 담았던 구매 리워드를, 펀딩이 종료된 경우에 한해
        qty만큼 반복하여 응답용 아이템으로 확장한다.
        - 모델 추정: pays.PaymentReward (payment FK, reward FK, cqy:int)
        - 유연성: 필드명이 다르면 qty/quantity도 순차적으로 시도
        - 상태: payment.status = DONE 이고 payment.funding.status ∈ {SUCCEEDED, FAILED}
        - 카테고리: LEVEL은 제외, GIFT/COUPON만 해당
        """
        out: list[dict] = []

        # pays.PaymentReward 모델을 동적으로 얻어와서, 존재하지 않으면 skip
        try:
            PaymentReward = django_apps.get_model("pays", "PaymentReward")
        except Exception:
            return out
        if PaymentReward is None:
            return out

        qs = (
            PaymentReward.objects
            .select_related("reward", "payment", "payment__funding")
            .filter(
                payment__user_id=self.request.user.id,
                payment__status=PaymentStatusChoices.DONE,
                payment__funding__status__in=FundingStatusChoices.SUCCEEDED,
            )
            .order_by("-pk")
        )

        for item in qs:
            reward = getattr(item, "reward", None)
            payment = getattr(item, "payment", None)
            funding = getattr(payment, "funding", None)

            if not (reward and funding):
                continue

            # LEVEL은 구매리워드 취지에 맞지 않으므로 제외
            # (쿼리 파라미터 cat 이 주어졌다면 그에 맞춰 필터)
            rcat = getattr(reward, "category", None)
            if rcat == "LEVEL":
                continue
            if cat and rcat != cat:
                continue

            # 수량 필드 탐색: cqy -> qty -> quantity
            qty = (
                getattr(item, "qty", None)
                or getattr(item, "quantity", None)
                or 1
            )
            try:
                qty = int(qty)
            except Exception:
                qty = 1
            qty = max(qty, 1)

            base = {
                # 구매건은 실체 쿠폰 id가 없을 수 있어 가상 id 부여 (충돌 방지 프리픽스)
                "id": f"purchase:{getattr(item, 'id', 'x')}",
                "category": reward.get_category_display(),         # "펀딩 할인쿠폰" 등
                "business_name": getattr(funding, "business_name", None),
                "title": getattr(reward, "title", ""),
                "content": getattr(reward, "content", ""),
                "amount": getattr(reward, "amount", 0),
            }

            # qty만큼 조건문 (각 아이템에 시퀀스 붙여 고유화)
            for i in range(qty):
                out.append({**base, "id": f"{base['id']}#{i+1}"})

        return out

    @require_profile(ProfileChoices.proposer)
    def get(self, category: Optional[str]) -> Dict[str, List[dict]]:
        cat = self._validate_and_norm_category(category)

        # 내가 보유한 리워드들
        prs = (
            ProposerReward.objects
            .filter(user=self.request.user.proposer)
            .select_related("reward", "reward__funding")
            .order_by("-pk")
        )

        funding_rewards: List[dict] = []
        level_rewards: List[dict] = []

        for pr in prs:
            r = pr.reward
            if not r:
                continue

            # 공통 필드
            base = {
                "id": pr.id,                           # ProposerReward.id (nanoid)
                "category": r.get_category_display(),  # 한글 라벨
                "title": r.title,
                "content": r.content,
                "amount": r.amount,
            }

            if r.category == RewardCategoryChoices.LEVEL:
                # 쿼리 파라미터 필터
                if cat and cat != "LEVEL":
                    continue
                level_rewards.append(base)
            else:
                # 펀딩 리워드(GIFT/COUPON)
                if cat and r.category != cat:
                    continue
                f = getattr(r, "funding", None)
                funding_rewards.append({
                    **base,
                    "business_name": getattr(f, "business_name", None),
                })

        return {"funding_rewards": funding_rewards, "level_rewards": level_rewards}

