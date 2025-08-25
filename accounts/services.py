from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple, DefaultDict
from collections import defaultdict
from datetime import timedelta

from django.apps import apps as django_apps
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

# ── 가중치/캡: 새 정책 ─────────────────────────────────────────────────────
#  - visits(지역 방문일수) 40%
#  - likes(해당 지역 좋아요 수) 20%
#  - proposals(해당 지역 제안 수) 20%
#  - fundings(해당 지역 펀딩 참여 수) 20%
LEVEL_WEIGHTS = getattr(settings, "LEVEL_WEIGHTS", {
    "visits":    40,  # 방문일수
    "likes":     20,  # 좋아요
    "proposals": 20,  # 제안
    "fundings":  20,  # 펀딩 참여
})
LEVEL_CAPS = getattr(settings, "LEVEL_CAPS", {
    "visits":    7,   # 1일 1회, 최대 7일
    "likes":     10,  # 최대 10회
    "proposals": 5,   # 최대 5회
    "fundings":  3,   # 최대 3회
})

DEFAULT_WINDOW_DAYS = int(getattr(settings, "LEVEL_WINDOW_DAYS", 7))  # 기본 7일(주 단위)

# ── 타입/헬퍼 ──────────────────────────────────────────────────────────────
AddrT = Tuple[str, str, str]  # (sido, sigungu, eupmyundong)

def _canon_addr(addr: dict | None) -> Optional[AddrT]:
    if not isinstance(addr, dict):
        return None
    s, g, e = addr.get("sido"), addr.get("sigungu"), addr.get("eupmyundong")
    if not (s and g and e):
        return None
    return (str(s), str(g), str(e))

def _now():
    return timezone.now()

def _window_7_days(end: Optional[timezone.datetime] = None) -> Tuple[timezone.datetime, timezone.datetime]:
    end = end or _now()
    start = end - timedelta(days=DEFAULT_WINDOW_DAYS)
    return (start, end)

def _score_to_level(score: float) -> int:
    # 0~29: Lv1 / 30~59: Lv2 / 60~100: Lv3
    if score >= 60:
        return 3
    if score >= 30:
        return 2
    return 1

@dataclass
class RegionStats:
    visits: int = 0       # cap 7
    likes: int = 0        # cap 10
    proposals: int = 0    # cap 5
    fundings: int = 0     # cap 3

    def clamped(self) -> "RegionStats":
        return RegionStats(
            visits=min(self.visits, LEVEL_CAPS["visits"]),
            likes=min(self.likes, LEVEL_CAPS["likes"]),
            proposals=min(self.proposals, LEVEL_CAPS["proposals"]),
            fundings=min(self.fundings, LEVEL_CAPS["fundings"]),
        )

    def to_score(self) -> int:
        c = self.clamped()
        score = 0.0
        score += (c.visits    / LEVEL_CAPS["visits"])    * LEVEL_WEIGHTS["visits"]    # (방문/7)*40
        score += (c.likes     / LEVEL_CAPS["likes"])     * LEVEL_WEIGHTS["likes"]     # (좋아요/10)*20
        score += (c.proposals / LEVEL_CAPS["proposals"]) * LEVEL_WEIGHTS["proposals"] # (제안/5)*20
        score += (c.fundings  / LEVEL_CAPS["fundings"])  * LEVEL_WEIGHTS["fundings"]  # (펀딩/3)*20
        return int(round(score))


# ── 핵심 서비스 ────────────────────────────────────────────────────────────
class ProposerWeeklyLevelComputer:
    """
    최근 7일(혹은 지정 윈도우) 기준으로
    Proposer 동(읍·면·동) 레벨 산정 → accounts.ProposerLevel 반영.
    * 새 정책: 방문일수·좋아요·제안·펀딩참여만 반영(각각 40/20/20/20).
    """

    def __init__(self,
                 window_start: Optional[timezone.datetime] = None,
                 window_end: Optional[timezone.datetime] = None):
        if window_start and window_end:
            self.window = (window_start, window_end)
        else:
            self.window = _window_7_days(window_end)

        self.Proposer        = django_apps.get_model("accounts", "Proposer")
        self.ProposerLevel   = django_apps.get_model("accounts", "ProposerLevel")
        self.LocationHistory = django_apps.get_model("accounts", "LocationHistory")

        self.Proposal             = django_apps.get_model("proposals", "Proposal")
        self.ProposerLikeProposal = django_apps.get_model("proposals", "ProposerLikeProposal")

        self.Payment = django_apps.get_model("pays", "Payment")
        self.Funding = django_apps.get_model("fundings", "Funding")

    # ── 공개 진입점 ────────────────────────────────────────────────────
    def run(self, only_proposer_ids: Optional[Iterable[str]] = None) -> Dict[str, int]:
        """
        Returns: {proposer_id: updated_rows_count}
        """
        updated: Dict[str, int] = {}
        base_qs = self.Proposer.objects.select_related("user")
        if only_proposer_ids:
            base_qs = base_qs.filter(id__in=list(only_proposer_ids))

        for proposer in base_qs.iterator():
            regions = self._collect_regions_for_proposer(proposer)
            if not regions:
                continue
            stats_map = self._build_region_stats(proposer, regions)
            n = self._upsert_levels(proposer, stats_map)
            updated[proposer.id] = n
        return updated

    # ── region 후보 모으기 ────────────────────────────────────────────
    def _collect_regions_for_proposer(self, proposer) -> List[AddrT]:
        start, end = self.window
        regions: set[AddrT] = set()

        # 1) 위치 기록(최근 7일 내)
        for row in self.LocationHistory.objects.filter(
            user=proposer, created_at__gte=start, created_at__lt=end
        ).only("address"):
            a = _canon_addr(row.address)
            if a:
                regions.add(a)

        # 2) 제안/좋아요/펀딩 참여가 있었던 지역
        # 제안
        for row in self.Proposal.objects.filter(
            user=proposer, created_at__gte=start, created_at__lt=end
        ).only("address"):
            a = _canon_addr(getattr(row, "address", None))
            if a:
                regions.add(a)

        # 좋아요(제안) - created_at 없을 수 있으니 방어
        like_qs = self.ProposerLikeProposal.objects.filter(user=proposer)
        try:
            like_qs = like_qs.filter(created_at__gte=start, created_at__lt=end)
        except Exception:
            like_qs = like_qs.none()
        for lk in like_qs.select_related("proposal").only("proposal__address"):
            a = _canon_addr(getattr(getattr(lk, "proposal", None), "address", None))
            if a:
                regions.add(a)

        # 펀딩 참여(Payment.status='DONE' & approved_at ∈ window)
        pay_qs = self.Payment.objects.filter(
            user=proposer, status="DONE",
            approved_at__gte=start, approved_at__lt=end,
        ).select_related("funding", "funding__proposal")
        for p in pay_qs.only("funding__proposal__address"):
            a = _canon_addr(getattr(getattr(getattr(p, "funding", None), "proposal", None), "address", None))
            if a:
                regions.add(a)

        return list(regions)

    # ── 지표 집계 ─────────────────────────────────────────────────────
    def _build_region_stats(self, proposer, regions: List[AddrT]) -> Dict[AddrT, RegionStats]:
        start, end = self.window
        stats: Dict[AddrT, RegionStats] = {r: RegionStats() for r in regions}

        # 방문일수(최근 7일, 하루 1회)
        hist = self.LocationHistory.objects.filter(
            user=proposer, created_at__gte=start, created_at__lt=end
        ).only("created_at", "address").order_by("created_at")
        visited_days = defaultdict(set)
        for row in hist:
            a = _canon_addr(row.address)
            if a:
                visited_days[a].add(row.created_at.date())
        for a, days in visited_days.items():
            if a in stats:
                stats[a].visits = len(days)

        # 주소 필터 맵
        addr_q = {a: Q(address__sido=a[0], address__sigungu=a[1], address__eupmyundong=a[2]) for a in regions}

        # 제안 수
        for a, q in addr_q.items():
            stats[a].proposals = self.Proposal.objects.filter(
                user=proposer, created_at__gte=start, created_at__lt=end
            ).filter(q).count()

        # 좋아요 수 (created_at 없을 가능성 방어)
        base_like = self.ProposerLikeProposal.objects.filter(user=proposer)
        has_like_created_at = True
        try:
            base_like.model._meta.get_field("created_at")
        except Exception:
            has_like_created_at = False

        for a in regions:
            q = Q(proposal__address__sido=a[0], proposal__address__sigungu=a[1], proposal__address__eupmyundong=a[2])
            lk = base_like.filter(q)
            if has_like_created_at:
                lk = lk.filter(created_at__gte=start, created_at__lt=end)
            else:
                lk = lk.none()
            stats[a].likes = lk.count()

        # 펀딩 참여 수 (status='DONE', approved_at ∈ window)
        for a in regions:
            q = Q(funding__proposal__address__sido=a[0],
                funding__proposal__address__sigungu=a[1],
                funding__proposal__address__eupmyundong=a[2])
            stats[a].fundings = self.Payment.objects.filter(
                user=proposer, status="DONE",
                approved_at__gte=start, approved_at__lt=end,
            ).filter(q).count()

        return stats
    # ── 레벨 저장 ─────────────────────────────────────────────────────
    def _upsert_levels(self, proposer, stats_map: Dict[AddrT, RegionStats]) -> int:
        """
        ProposerLevel (user, address{...}) 존재 시 update, 없으면 create.
        Returns: updated_or_created_rows_count
        """
        updated = 0
        for a, st in stats_map.items():
            score = st.to_score()
            level = _score_to_level(score)

            sido, sigungu, eup = a
            row = self.ProposerLevel.objects.filter(
                user=proposer,
                address__sido=sido,
                address__sigungu=sigungu,
                address__eupmyundong=eup,
            ).order_by("-id").first()

            if row:
                if row.level != level:
                    row.level = level
                    row.save(update_fields=["level"])
                updated += 1
            else:
                self.ProposerLevel.objects.create(
                    user=proposer,
                    address={"sido": sido, "sigungu": sigungu, "eupmyundong": eup},
                    level=level,
                )
                updated += 1
        return updated
