from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Iterable, DefaultDict
from collections import defaultdict
from datetime import timedelta, datetime
from django.utils import timezone as tz

from django.apps import apps as django_apps
from django.db import transaction

from .models import Proposer, ProposerLevel, LocationHistory
from utils.choices import PaymentStatusChoices


# ─────────────────────────────────────────────────────────────────────────────
# 설정/헬퍼
# ─────────────────────────────────────────────────────────────────────────────
Addr = Tuple[str, str, str]  # (sido, sigungu, eupmyundong)


@dataclass(frozen=True)
class LevelWeights:
    """명세 기반 가중치/상한."""
    VISIT_WEIGHT: int = 40     # 방문 빈도 40%
    PROPOSAL_WEIGHT: int = 20  # 제안 수 20%
    ACTIVITY_WEIGHT: int = 20  # 활동(좋아요+펀딩) 20%
    VISIT_CAP: int = 7         # 1일 1회 기준 주 최대 7
    PROPOSAL_CAP: int = 10     # 주 최대 10
    ACTIVITY_CAP: int = 10     # 주 최대 10


def _week_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or tz.now()
    local = tz.localtime(now)
    start = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return start, end



def _norm_addr(addr_json: dict | None) -> Optional[Addr]:
    """주소 JSON에서 (시/도, 시/군/구, 읍/면/동)만 추려 표준 튜플로 정규화."""
    if not isinstance(addr_json, dict):
        return None
    sido = addr_json.get("sido")
    sigungu = addr_json.get("sigungu")
    eup = addr_json.get("eupmyundong")
    if not (sido and sigungu and eup):
        return None
    return (str(sido), str(sigungu), str(eup))


def _score_to_level(total_points: int) -> int:
    """
    점수 → 레벨 매핑
    - 0~29:  Lv.1
    - 30~59: Lv.2
    - 60~100: Lv.3
    """
    if total_points < 30:
        return 1
    if total_points < 60:
        return 2
    return 3


# ─────────────────────────────────────────────────────────────────────────────
# 핵심 서비스
# ─────────────────────────────────────────────────────────────────────────────
class ProposerLevelingService:
    """
    주간 활동을 주소(구/동) 단위로 모아 점수 계산 후 ProposerLevel을 upsert.
    계산식(명세):
        (방문횟수/7 * 40) + (제안수/10 * 20) + ((좋아요+펀딩)/10 * 20)
      - 각 항목의 분수는 1을 상한으로 캡핑
      - 체류 시간(30%) 항목은 GPS 체류 로그 모델이 생기면 확장
    """

    def __init__(self, *, start: datetime | None = None, end: datetime | None = None,
                weights: LevelWeights | None = None):
        self.start, self.end = (start, end) if (start and end) else _week_window()
        self.w = weights or LevelWeights()

        # 외부 앱 모델 지연 로딩(순환 참조 방지)
        self.Proposal = django_apps.get_model("proposals", "Proposal")
        self.ProposerLikeFunding = django_apps.get_model("fundings", "ProposerLikeFunding")
        self.Payment = django_apps.get_model("pays", "Payment")

    # ── 집계(이번 주) ────────────────────────────────────────────────────
    def _visits_by_addr(self, proposer: Proposer) -> Dict[Addr, int]:
        """
        방문 횟수: LocationHistory에서 날짜 단위로 '하루 최대 1회'로 처리 → 주간 합산, 상한 7.
        """
        rows = (
            LocationHistory.objects
            .filter(user=proposer, created_at__gte=self.start, created_at__lt=self.end)
            .only("created_at", "address")
            .order_by("created_at")
        )
        per_addr_dates: DefaultDict[Addr, set] = defaultdict(set)
        for r in rows:
            addr = _norm_addr(r.address)
            if not addr:
                continue
            local_date = tz.localtime(r.created_at).date()
            per_addr_dates[addr].add(local_date)  
        return {addr: min(len(dates), self.w.VISIT_CAP) for addr, dates in per_addr_dates.items()}

    def _proposals_by_addr(self, proposer: Proposer) -> Dict[Addr, int]:
        """제안 수: proposals.Proposal(작성자=proposer)의 이번 주 생성 건."""
        q = (
            self.Proposal.objects
            .filter(user=proposer, created_at__gte=self.start, created_at__lt=self.end)
            .only("address", "created_at")
        )
        cnt: DefaultDict[Addr, int] = defaultdict(int)
        for p in q:
            addr = _norm_addr(getattr(p, "address", None))
            if addr:
                cnt[addr] += 1
        return {a: min(n, self.w.PROPOSAL_CAP) for a, n in cnt.items()}

    def _likes_by_addr(self, proposer: Proposer) -> Dict[Addr, int]:
        """좋아요 수: fundings.ProposerLikeFunding(user=proposer) 이번 주.
        주소 기준은 '좋아요한 펀딩의 proposal.address'."""
        q = (
            self.ProposerLikeFunding.objects
            .select_related("funding", "funding__proposal")
            .filter(user=proposer, created_at__gte=self.start, created_at__lt=self.end)
        )
        cnt: DefaultDict[Addr, int] = defaultdict(int)
        for lk in q:
            prop = getattr(getattr(lk, "funding", None), "proposal", None)
            addr = _norm_addr(getattr(prop, "address", None) if prop else None)
            if addr:
                cnt[addr] += 1
        return cnt  # 최종 합산 시 캡핑

    def _pays_by_addr(self, proposer: Proposer) -> Dict[Addr, int]:
        """펀딩 참여 수: pays.Payment(DONE, user=proposer) 이번 주 승인 건.
        주소 기준은 '결제한 펀딩의 proposal.address'."""
        q = (
            self.Payment.objects
            .select_related("funding", "funding__proposal")
            .filter(
                user=proposer,
                status=PaymentStatusChoices.DONE,
                approved_at__gte=self.start, approved_at__lt=self.end,
            )
        )
        cnt: DefaultDict[Addr, int] = defaultdict(int)
        for pay in q:
            prop = getattr(getattr(pay, "funding", None), "proposal", None)
            addr = _norm_addr(getattr(prop, "address", None) if prop else None)
            if addr:
                cnt[addr] += 1
        return cnt

    # ── 점수 → 레벨 ─────────────────────────────────────────────────────
    def _calc_points(self, *, visit: int, proposal: int, like: int, pay: int) -> int:
        visit_points = min(visit / float(self.w.VISIT_CAP or 1), 1.0) * self.w.VISIT_WEIGHT
        prop_points  = min(proposal / float(self.w.PROPOSAL_CAP or 1), 1.0) * self.w.PROPOSAL_WEIGHT
        act_raw = like + pay
        act_points   = min(act_raw / float(self.w.ACTIVITY_CAP or 1), 1.0) * self.w.ACTIVITY_WEIGHT
        total = visit_points + prop_points + act_points  # 현재 상한 80
        return int(round(max(0, min(100, total))))

    def _upsert_level(self, proposer: Proposer, addr: Addr, level: int) -> None:
        """ProposerLevel(address JSON 정확히 매칭) upsert."""
        sido, sigungu, eup = addr
        addr_json = {"sido": sido, "sigungu": sigungu, "eupmyundong": eup}
        obj, created = ProposerLevel.objects.get_or_create(
            user=proposer,
            address=addr_json,
            defaults={"level": level},
        )
        if not created and obj.level != level:
            obj.level = level
            obj.save(update_fields=["level"])

    # ── 엔트리포인트 ─────────────────────────────────────────────────────
    @transaction.atomic
    def run_for_proposer(self, proposer: Proposer) -> dict:
        """단일 사용자 갱신. 디버그용으로 주소별 산출치도 반환."""
        visits   = self._visits_by_addr(proposer)
        props    = self._proposals_by_addr(proposer)
        likes    = self._likes_by_addr(proposer)
        pays     = self._pays_by_addr(proposer)

        results: dict[Addr, dict] = {}
        for addr in (set(visits) | set(props) | set(likes) | set(pays)):
            v  = visits.get(addr, 0)
            pr = props.get(addr, 0)
            lk = likes.get(addr, 0)
            py = pays.get(addr, 0)
            points = self._calc_points(visit=v, proposal=pr, like=lk, pay=py)
            level  = _score_to_level(points)
            self._upsert_level(proposer, addr, level)
            results[addr] = {"visit": v, "proposal": pr, "like": lk, "pay": py, "points": points, "level": level}
        return results

    @transaction.atomic
    def run_for_all(self, queryset: Optional[Iterable[Proposer]] = None) -> None:
        """전체 사용자 갱신."""
        qs = queryset or Proposer.objects.all().select_related("user")
        for p in qs:
            self.run_for_proposer(p)

