from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple, DefaultDict
from collections import defaultdict
from datetime import timedelta

from django.apps import apps as django_apps
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

LEVEL_WEIGHTS = getattr(settings, "LEVEL_WEIGHTS", {
    "visit_days": 40,   # 방문 빈도
    "stay_hours": 30,   # 체류 시간
    "activity":  20,    # 활동 기여
    "recency":   10,    # 최근 접속
})
LEVEL_CAPS = getattr(settings, "LEVEL_CAPS", {
    "visit_days": 7,    # 7일
    "stay_hours": 20,   # 20시간
    "activity":  10,    # 10회
})
STAY_GAP_MAX_MINUTES = int(getattr(settings, "STAY_GAP_MAX_MINUTES", 60))  # 인접 로그 간격 허용치
DEFAULT_WINDOW_DAYS = int(getattr(settings, "LEVEL_WINDOW_DAYS", 7))

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
    if score >= 60:
        return 3
    if score >= 30:
        return 2
    return 1

@dataclass
class RegionStats:
    visit_days: int = 0         # (cap 7)
    stay_hours: float = 0.0     # (cap 20)
    activity: int = 0           # (cap 10)
    recency: int = 0            # 0 or 1

    def clamped(self) -> "RegionStats":
        return RegionStats(
            visit_days=min(self.visit_days, LEVEL_CAPS["visit_days"]),
            stay_hours=min(self.stay_hours, LEVEL_CAPS["stay_hours"]),
            activity=min(self.activity, LEVEL_CAPS["activity"]),
            recency=1 if self.recency else 0,
        )

    def to_score(self) -> int:
        c = self.clamped()
        score = 0.0
        # 방문 빈도
        score += (c.visit_days / LEVEL_CAPS["visit_days"]) * LEVEL_WEIGHTS["visit_days"]
        # 체류 시간
        score += (c.stay_hours / LEVEL_CAPS["stay_hours"]) * LEVEL_WEIGHTS["stay_hours"]
        # 활동 기여
        score += (c.activity / LEVEL_CAPS["activity"]) * LEVEL_WEIGHTS["activity"]
        # 최근성
        score += (c.recency * LEVEL_WEIGHTS["recency"])
        return int(round(score))


# ── 핵심 서비스 ────────────────────────────────────────────────────────────
class ProposerWeeklyLevelComputer:
    """
    최근 7일(또는 주어진 윈도우) 기준으로
    Proposer × 동(읍·면·동) 레벨을 산정해 ProposerLevel에 반영.
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

        self.Proposal              = django_apps.get_model("proposals", "Proposal")
        self.ProposerLikeProposal  = django_apps.get_model("proposals", "ProposerLikeProposal")

        self.Payment  = django_apps.get_model("pays", "Payment")
        self.Funding  = django_apps.get_model("fundings", "Funding")
        self.PmtStat  = django_apps.get_model("utils", "PaymentStatusChoices") if False else None  # placeholder
        # PaymentStatusChoices는 Enum class 이므로 아래 쿼리에서 직접 문자열 사용

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

        # 1) 위치 기록
        for row in self.LocationHistory.objects.filter(
            user=proposer, created_at__gte=start, created_at__lt=end
        ).only("address"):
            a = _canon_addr(row.address)
            if a:
                regions.add(a)

        # 2) 제안/좋아요/펀딩참여가 있었던 동 주소
        # 제안
        for row in self.Proposal.objects.filter(
            user=proposer, created_at__gte=start, created_at__lt=end
        ).only("address"):
            a = _canon_addr(getattr(row, "address", None))
            if a:
                regions.add(a)

        # 좋아요(제안) - created_at 필드가 없을 수도 있으니 방어
        like_qs = self.ProposerLikeProposal.objects.filter(user=proposer)
        try:
            like_qs = like_qs.filter(created_at__gte=start, created_at__lt=end)
        except Exception:
            # created_at이 없다면, '최근 7일 내 좋아요'를 정확히 알 수 없으므로 region 후보만 추출하지 않음
            like_qs = like_qs.none()
        for lk in like_qs.select_related("proposal").only("proposal__address"):
            a = _canon_addr(getattr(getattr(lk, "proposal", None), "address", None))
            if a:
                regions.add(a)

        # 펀딩 참여(Payment.status=DONE & approved_at ∈ window)
        pay_qs = self.Payment.objects.filter(
            user=proposer,
            status="DONE",  # PaymentStatusChoices.DONE
            approved_at__gte=start,
            approved_at__lt=end,
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

        # A) 방문(일수) & 체류(시간)
        #  - 같은 사용자/윈도우의 LocationHistory 전체를 시간순으로 읽고,
        #  - Δt를 "이전 레코드의 지역"에 귀속(같은 지역 + Δt <= threshold 일 때만 체류로 인정)
        hist = list(
            self.LocationHistory.objects.filter(
                user=proposer, created_at__gte=start, created_at__lt=end
            ).only("created_at", "address").order_by("created_at")
        )

        # 방문일수: 지역별 날짜 set
        visited_days: DefaultDict[AddrT, set] = defaultdict(set)

        prev_addr: Optional[AddrT] = None
        prev_ts: Optional[timezone.datetime] = None
        for row in hist:
            a = _canon_addr(row.address)
            ts = row.created_at
            if a:
                visited_days[a].add(ts.date())

            if prev_addr and prev_ts and a == prev_addr:
                dt_min = (ts - prev_ts).total_seconds() / 60.0
                if 0 < dt_min <= STAY_GAP_MAX_MINUTES:
                    stats[a].stay_hours += (dt_min / 60.0)

            prev_addr, prev_ts = a, ts

        for a, days in visited_days.items():
            if a in stats:
                stats[a].visit_days = len(days)

        # B) 활동 기여 (제안/좋아요/펀딩)
        #   - 모두 "해당 지역 주소 + 최근 7일" 기준
        #   - 효율 위해 region -> Q 주소필터 맵을 만들어 중복 필터 재사용
        addr_filters: Dict[AddrT, Q] = {
            a: Q(address__sido=a[0], address__sigungu=a[1], address__eupmyundong=a[2])
            for a in regions
        }
        prop_counts: Dict[AddrT, int] = {a: 0 for a in regions}
        like_counts: Dict[AddrT, int] = {a: 0 for a in regions}
        pay_counts:  Dict[AddrT, int] = {a: 0 for a in regions}

        # 제안 수
        for a, q in addr_filters.items():
            prop_counts[a] = self.Proposal.objects.filter(
                user=proposer, created_at__gte=start, created_at__lt=end
            ).filter(q).count()

        # 좋아요 수 (created_at 없을 가능성 방어)
        base_like_qs = self.ProposerLikeProposal.objects.filter(user=proposer)
        like_has_created_at = True
        try:
            _ = base_like_qs.model._meta.get_field("created_at")
        except Exception:
            like_has_created_at = False

        for a in regions:
            q = Q(proposal__address__sido=a[0], proposal__address__sigungu=a[1], proposal__address__eupmyundong=a[2])
            lk_qs = base_like_qs.filter(q)
            if like_has_created_at:
                lk_qs = lk_qs.filter(created_at__gte=start, created_at__lt=end)
            else:
                # created_at이 없으면, “최근 7일 내 좋아요”를 판별할 수 없으므로 0으로 둠
                lk_qs = lk_qs.none()
            like_counts[a] = lk_qs.count()

        # 펀딩 참여 수 (Payment.status='DONE' & approved_at)
        for a in regions:
            q = Q(funding__proposal__address__sido=a[0],
                  funding__proposal__address__sigungu=a[1],
                  funding__proposal__address__eupmyundong=a[2])
            pay_counts[a] = self.Payment.objects.filter(
                user=proposer,
                status="DONE",
                approved_at__gte=start, approved_at__lt=end,
            ).filter(q).count()

        for a in regions:
            stats[a].activity = prop_counts[a] + like_counts[a] + pay_counts[a]

        # C) 최근성(최근 7일 접속 여부)
        last_login = getattr(getattr(proposer, "user", None), "last_login", None)
        recency = 1 if (last_login and (end - last_login) <= timedelta(days=DEFAULT_WINDOW_DAYS)) else 0
        for a in regions:
            stats[a].recency = recency

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
            # 동일 주소 행 존재하면 업데이트(여러 개면 가장 최근 것 1개만)
            row = self.ProposerLevel.objects.filter(
                user=proposer,
                address__sido=sido,
                address__sigungu=sigungu,
                address__eupmyundong=eup,
            ).order_by("-id").first()

            if row:
                if row.level != level:
                    row.level = level
                    # updated_at이 없다면 save만; 있다면 자동 갱신
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