from __future__ import annotations
from typing import List, Dict, Optional
from django.db.models import QuerySet, Count, Max, Sum
from dataclasses import dataclass
from datetime import datetime
from django.utils import timezone
from datetime import timedelta
from django.http import HttpRequest
from django.db import transaction
from collections import defaultdict
from rest_framework.exceptions import PermissionDenied
from utils.choices import ProfileChoices, FundingStatusChoices, PaymentStatusChoices, IndustryChoices, RewardCategoryChoices, RewardStatusChoices
from utils.decorators.service import require_profile
from utils.helpers import resolve_viewer_addr
from django.apps import apps as django_apps  
from django.core.exceptions import FieldError, ImproperlyConfigured
from .models import Funding, ProposerLikeFunding, ProposerScrapFunding, FounderScrapFunding, ProposerReward, Reward
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

    base = {"has_paid": False, "can_cancel": False, "last_paid_at": None}

    if not getattr(user, "is_authenticated", False):
        return base
    
    proposer = getattr(user, "proposer", None)
    if proposer is None:
        return base

    qs = Payment.objects.filter(
        funding_id=funding.id,
        user_id=proposer.id, 
        status=PaymentStatusChoices.DONE,
    )

    # 마지막 결제(승인) 시각
    last_payment = qs.order_by("-approved_at", "-pk").first()
    if not last_payment:
        return base
    
    # 결제 이력 존재
    base["has_paid"] = True
    # last_paid_at: ISO8601(+TZ)로 직렬화
    if last_payment.approved_at:
        base["last_paid_at"] = timezone.localtime(last_payment.approved_at).isoformat()

        # 승인 후 7일 내 취소 가능
        base["can_cancel"] = (timezone.now() - last_payment.approved_at) <= CANCELABLE_WINDOW

    return base

# schedule 중 end 값만
def _schedule_end_dt(funding):
    try:
        return timezone.make_aware(datetime.strptime(funding.schedule["end"], "%Y-%m-%d"))
    except Exception:
        return None
    
# build_actions_block()에서 my_payment["last_paid_at"]는 지금 ISO 문자열인데, 여기에 바로 timezone.now() - ...를 빼고 있어요. 이건 타입 에러 납니다. 파싱해서 비교하도록 고쳐주세요:
def _parse_iso_to_aware(dt_str: str):
    try:
        dt = datetime.fromisoformat(dt_str)  # "2025-08-18T16:40:12+09:00"
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
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
    last_paid_raw = my_payment.get("last_paid_at") if my_payment else None
    last_paid_at = _parse_iso_to_aware(last_paid_raw) if isinstance(last_paid_raw, str) else last_paid_raw
    if last_paid_at:
        can_cancel_last_payment = (now - last_paid_at) <= CANCELABLE_WINDOW

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
    
    @require_profile(ProfileChoices.proposer)    #403
    def get_for_proposer(self, funding_id: int) -> dict:
        funding = self._get_funding(funding_id, ProfileChoices.proposer.value)
        my_payment = build_my_payment_block(funding, self.request.user)
        viewer_addr = resolve_viewer_addr(self.request.user, ProfileChoices.proposer.value)  
        ser = FundingDetailProposerSerializer(
            funding,
            context={
                "request": self.request,
                "profile": ProfileChoices.proposer.value,
                "my_payment": my_payment,
                "viewer_addr": viewer_addr,
            },
        )
        return ser.data

    @require_profile(ProfileChoices.founder)    #403
    def get_for_founder(self, funding_id: int) -> dict:
        funding = self._get_funding(funding_id, ProfileChoices.founder.value)
        likes_analysis = build_likes_analysis(funding)
        viewer_addr = resolve_viewer_addr(self.request.user, ProfileChoices.founder.value)
        ser = FundingDetailFounderSerializer(
            funding,
            context={
                "request": self.request,
                "profile": ProfileChoices.founder.value,
                "likes_analysis": likes_analysis,
                "viewer_addr": viewer_addr, 
            },
        )
        return ser.data
    

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
                payment__user_id=proposer.id,                 # ← CHANGED (기존: self.request.user.id)
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
    
    
    def _serialize_response(
        self, prs_qs, cat: Optional[str]
    ) -> Dict[str, List[dict]]:
        """
        ProposerReward 쿼리셋을 명세 JSON으로 변환.
        - funding_rewards: GIFT/COUPON (+ business_name)
        - level_rewards:   LEVEL
        - ?category= 필터 적용
        """
        funding_rewards: List[dict] = []
        level_rewards: List[dict] = []

        for pr in prs_qs.select_related("reward", "reward__funding"):
            r = pr.reward
            if not r:
                continue

            base = {
                "id": pr.id,                           # ProposerReward.id (nanoid)
                "category": r.get_category_display(),  # "펀딩 할인쿠폰" / "펀딩 선물증정" / "레벨"
                "title": r.title,
                "content": r.content,
                "amount": r.amount,
            }

            if r.category == RewardCategoryChoices.LEVEL:
                if cat and cat != "LEVEL":
                    continue
                level_rewards.append(base)
            else:
                if cat and r.category != cat:
                    continue
                biz_name = getattr(getattr(r, "funding", None), "business_name", None)
                funding_rewards.append({**base, "business_name": biz_name})

        return {"funding_rewards": funding_rewards, "level_rewards": level_rewards}

    def _base_qs(self):
        proposer = getattr(self.request.user, "proposer", None)
        if proposer is None:
            raise PermissionDenied("제안자 프로필이 필요해요.")
        return ProposerReward.objects.filter(user=proposer)

    def get(self, category: Optional[str]) -> Dict[str, List[dict]]:
        # 0) 카테고리 검증
        cat = self._validate_and_norm_category(category)

        # 1) 보유 리워드 조회 후 직렬화
        prs_qs = self._base_qs().order_by("-pk")
        return self._serialize_response(prs_qs, cat)
    


def _schedule_end_dt(funding: Funding) -> Optional[datetime]:
    """
    schedule["end"]를 'YYYY-MM-DD'로 가정하고 해당 일자 00:00(로컬TZ)로 해석.
    - 설계 상 end는 '마감일 00:00'로 간주(= end 당일은 이미 마감).
    """
    try:
        end_str = (funding.schedule or {}).get("end")
        if not end_str:
            return None
        dt = datetime.strptime(end_str, "%Y-%m-%d")
        return timezone.make_aware(dt, timezone.get_current_timezone())
    except Exception:
        return None


@dataclass
class FundingSettlementResult:
    updated: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0  # end가 없거나 아직 미도래, 혹은 상태가 IN_PROGRESS가 아님


class FundingSettlementService:
    """
    자정 배치 등에서 호출:
      - IN_PROGRESS 펀딩 중 end를 지난 것 정산
      - 성공: (DONE 결제금액 합계) >= goal_amount
      - 실패: 그 외
    """

    def __init__(self, now: Optional[datetime] = None):
        self.now = now or timezone.now()
        self.Payment = django_apps.get_model("pays", "Payment")

    def _is_expired(self, funding: Funding) -> bool:
        end_dt = _schedule_end_dt(funding)
        return bool(end_dt and self.now >= end_dt)

    def _paid_amount(self, funding_id: int) -> int:
        agg = (
            self.Payment.objects
            .filter(funding_id=funding_id, status=PaymentStatusChoices.DONE)
            .aggregate(total=Sum("total_amount"))
        )
        return int(agg["total"] or 0)

    @transaction.atomic
    def settle_one(self, funding: Funding) -> Optional[str]:
        # 1) 상태/마감 검증
        if funding.status != FundingStatusChoices.IN_PROGRESS:
            return None
        if not self._is_expired(funding):
            return None

        # 2) 정산 결과 결정
        total_paid = self._paid_amount(funding.id)
        new_status = (
            FundingStatusChoices.SUCCEEDED
            if total_paid >= int(funding.goal_amount or 0)
            else FundingStatusChoices.FAILED
        )

        # 3) 경합 회피: 조건부 업데이트
        updated = (
            Funding.objects
            .filter(pk=funding.pk, status=FundingStatusChoices.IN_PROGRESS)
            .update(status=new_status)
        )
        if not updated:
            return None

        # 4) 성공 시에만 구매 리워드 발급
        if new_status == FundingStatusChoices.SUCCEEDED:
            self._materialize_purchased_rewards_for_funding(funding)

        return new_status
    
    def _materialize_purchased_rewards_for_funding(self, funding: Funding) -> None:
        """
        (정산 시점용) 펀딩이 SUCCEEDED 가 되면,
        이 펀딩에 대해 결제(DONE)한 제안자들에게 구매 리워드(GIFT/COUPON)를 수량만큼 발급.
        - idempotent: 기존 보유 수량과 구매 총량을 비교하여 '부족분'만 생성
        - LEVEL 보상은 제외
        """
        # 1) 이 펀딩에 대해 승인 완료된 결제들
        pays_qs = (
            Payment.objects
            .select_related("order", "user")  # user = accounts.Proposer
            .filter(
                funding=funding,
                status=PaymentStatusChoices.DONE,
            )
            .order_by("approved_at", "pk")
        )

        if not pays_qs.exists():
            return

        # 2) 사용자별·리워드별 필요 수량 집계: {(proposer_id, reward_id) -> qty}
        need_map: dict[tuple[int, int], int] = defaultdict(int)

        for p in pays_qs:
            proposer = getattr(p, "user", None)  # Payment.user = Proposer
            if proposer is None:
                continue
            order = getattr(p, "order", None)
            items = getattr(order, "items_json", []) if order else []
            for it in items:
                rid = it.get("reward_id")
                qty = it.get("quantity", 1)
                try:
                    rid = int(rid)
                    qty = int(qty)
                except Exception:
                    continue
                if qty <= 0:
                    continue
                need_map[(proposer.id, rid)] += qty

        if not need_map:
            return

        # 3) 리워드 메타 (LEVEL 제외 확인)
        reward_ids = {rid for (_, rid) in need_map.keys()}
        reward_map = {r.id: r for r in Reward.objects.filter(id__in=reward_ids)}

        # 4) 사용자·리워드별 이미 보유한 수량 파악 → 부족분만 생성
        to_create: list[ProposerReward] = []

        # 한번에 조회 최적화: (user_id, reward_id) 별 카운트 맵
        from django.db.models import Count
        existing = (
            ProposerReward.objects
            .filter(reward_id__in=reward_ids, user_id__in={uid for (uid, _) in need_map.keys()})
            .values("user_id", "reward_id")
            .annotate(cnt=Count("id"))
        )
        have_map = {(row["user_id"], row["reward_id"]): int(row["cnt"]) for row in existing}

        for (uid, rid), target_qty in need_map.items():
            r = reward_map.get(rid)
            if not r:
                continue
            if r.category == RewardCategoryChoices.LEVEL:
                # 구매 발급 대상 아님
                continue
            have = have_map.get((uid, rid), 0)
            need = max(int(target_qty) - int(have), 0)
            if need <= 0:
                continue
            # 부족분만큼 생성
            to_create.extend(
                ProposerReward(user_id=uid, reward_id=rid, status=RewardStatusChoices.AVAILABLE)
                for _ in range(need)
            )

        if to_create:
            ProposerReward.objects.bulk_create(to_create, ignore_conflicts=True)

    def run(self) -> FundingSettlementResult:
        result = FundingSettlementResult()
        qs = Funding.objects.only("id", "status", "goal_amount", "schedule").filter(
            status=FundingStatusChoices.IN_PROGRESS
        )

        for f in qs:
            # 마감 여부 확인
            if not self._is_expired(f):
                result.skipped += 1
                continue

            new_status = self.settle_one(f)  # SUCCEEDED/FAILED/None
            if new_status is None:
                result.skipped += 1
                continue

            result.updated += 1
            if new_status == FundingStatusChoices.SUCCEEDED:
                result.succeeded += 1
            else:
                result.failed += 1

        return result

    