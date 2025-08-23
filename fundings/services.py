from __future__ import annotations
from typing import Iterable, Tuple, Dict, Any
from django.db.models import QuerySet
from datetime import datetime
from django.utils import timezone
from datetime import timedelta
from django.http import HttpRequest
from rest_framework.exceptions import PermissionDenied
from utils.choices import ProfileChoices, FundingStatusChoices, PaymentStatusChoices
from utils.decorators import require_profile
from django.core.exceptions import FieldError, ImproperlyConfigured
from .models import Funding, ProposerLikeFunding, ProposerScrapFunding, FounderScrapFunding
from pays.models import Payment
from .serializers import (
    FundingListSerializer, 
    FundingMapSerializer, 
    RegionClusterSerializer,
    FundingDetailProposerSerializer, 
    FundingDetailFounderSerializer,
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
        ).order_by(
            '-proposer_scrap_funding__created_at',
        )
        serializer = FundingListSerializer(fundings, many=True)
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
        ).order_by(
            '-founder_scrap_funding__created_at',
        )
        serializer = FundingListSerializer(fundings, many=True)
        return serializer.data
    
def _extract_latlng(funding: Funding) -> Tuple[float | None, float | None]:
    pos = getattr(funding.proposal, 'position', None)
    if isinstance(pos, dict):
        lat = pos.get('latitude')
        lng = pos.get('longitude')
        try:
            return (float(lat), float(lng)) if lat is not None and lng is not None else (None, None)
        except (TypeError, ValueError):
            return (None, None)
    lat = getattr(funding.proposal, 'latitude', None)
    lng = getattr(funding.proposal, 'longitude', None)
    try:
        return (float(lat), float(lng)) if lat is not None and lng is not None else (None, None)
    except (TypeError, ValueError):
        return (None, None)

def _cluster(
    fundings: Iterable[Funding],
    level: str,  # 'sido' | 'sigungu' | 'eupmyundong'
) -> list[dict]:
    buckets: Dict[str, Dict[str, Any]] = {}
    for f in fundings:
        addr = getattr(f.proposal, 'address', {}) or {}
        key = addr.get(level)
        if not key:
            continue
        lat, lng = _extract_latlng(f)
        b = buckets.setdefault(key, {'count': 0, 'lat_sum': 0.0, 'lng_sum': 0.0, 'lat_n': 0, 'lng_n': 0})
        b['count'] += 1
        if lat is not None and lng is not None:
            b['lat_sum'] += lat
            b['lng_sum'] += lng
            b['lat_n'] += 1
            b['lng_n'] += 1

    items = sorted(buckets.items(), key=lambda kv: (-kv[1]['count'], kv[0]))
    out = []
    for i, (address, v) in enumerate(items, start=1):
        lat = (v['lat_sum'] / v['lat_n']) if v['lat_n'] > 0 else None
        lng = (v['lng_sum'] / v['lng_n']) if v['lng_n'] > 0 else None
        out.append({
            'id': i,
            'address': address,
            'position': {'latitude': lat, 'longitude': lng},
            'number': v['count'],
        })
    return out

class FundingMapService:
    """
    지도 조회 전용 서비스.
    - 무조건 IN_PROGRESS + with_analytics().with_proposal() 강제
    - zoom=0: 상세 리스트
    - zoom in (500/2000/10000): 집계
    """

    def __init__(self, request: HttpRequest):
        self.request = request

    def _base_qs(self) -> QuerySet[Funding]:
        return (Funding.objects
                .filter(status=FundingStatusChoices.IN_PROGRESS)
                .with_analytics()
                .with_proposal())

    def list_in_dong(self) -> list[dict]:
        """
        zoom=0: 진행중 펀딩 상세 리스트(동 이하)
        qparams: sido, sigungu, eupmyundong, industry, order
        """
        q = self.request.query_params
        sido = q.get('sido')
        sigungu = q.get('sigungu')
        eup = q.get('eupmyundong')
        industry = q.get('industry')
        order = q.get('order')

        qs = self._base_qs()

        if sido and sigungu and eup:
            qs = qs.filter(
                proposal__address__sido=sido,
                proposal__address__sigungu=sigungu,
                proposal__address__eupmyundong=eup,
            )

        if industry:
            qs = qs.filter(proposal__industry=industry)

        order_map = {
            '인기순': ('-likes_count', '-id'),
            '최신순': ('-id',),
            '레벨순': ('radius', '-id'),
        }
        qs = qs.order_by(*order_map.get(order, ('-id',)))

        return FundingMapSerializer(qs, many=True, context={'request': self.request}).data

    def cluster(self, zoom: int) -> list[dict]:
        """
        zoom in: 500/2000/10000 → 집계 응답
        """
        qs = self._base_qs()  # select_related(proposal) 포함
        if zoom == 10000:
            data = _cluster(qs, level='sido')
        elif zoom == 2000:
            data = _cluster(qs, level='sigungu')
        elif zoom == 500:
            data = _cluster(qs, level='eupmyundong')
        else:
            raise ValueError('허용되지 않은 zoom 값')
        return RegionClusterSerializer(data, many=True).data

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
    last_paid_at = last_payment.approved_at if last_payment else None

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
    """
    GET /fundings/{funding_id}/{profile}
    - queryset: with_analytics().with_proposal() 강제
    - serializer: FundingListSerializer 상속 시리얼라이저만 사용
    """
    def __init__(self, request: HttpRequest):
        self.request = request

    def _get_funding(self, funding_id: int) -> Funding:
        return (
            Funding.objects
            .with_analytics()
            .with_proposal()
            .select_related("user", "proposal")
            .prefetch_related("reward")
            .get(id=funding_id)
        )

    def get(self, funding_id: int, profile: str) -> dict:
        funding = self._get_funding(funding_id)
        profile = profile.lower()

        if profile == ProfileChoices.proposer.value:
            my_payment = build_my_payment_block(funding, self.request.user)
            ser = FundingDetailProposerSerializer(
                funding, context={"request": self.request, "my_payment": my_payment}
            )
            return ser.data

        if profile == ProfileChoices.founder.value:
            likes_analysis = build_likes_analysis(funding)
            ser = FundingDetailFounderSerializer(
                funding, context={"request": self.request, "likes_analysis": likes_analysis}
            )
            return ser.data

        raise PermissionDenied("허용되지 않은 profile 입니다. (founder|proposer)")
    


