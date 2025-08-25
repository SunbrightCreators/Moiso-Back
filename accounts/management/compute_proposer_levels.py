from __future__ import annotations
from django.utils import timezone
from datetime import datetime
from accounts.services import ProposerWeeklyLevelComputer

def compute_proposer_levels(start_raw: str | None = None,
                            end_raw: str | None = None,
                            ids: list[str] | None = None) -> dict[str, int]:
    """
    최근 7일(or 주어진 윈도우) 기준으로 Proposer 지역 레벨을 산정/업데이트합니다.
    Args:
        start_raw (str|None): ISO 포맷 시작 시각 (예: 2025-08-18T00:00:00+09:00)
        end_raw   (str|None): ISO 포맷 끝 시각   (예: 2025-08-25T00:00:00+09:00)
        ids       (list[str]|None): 특정 proposer id(nanoid) 리스트
    Returns:
        dict[str, int]: {proposer_id: updated_rows_count}
    """

    def _parse_iso(s: str):
        try:
            # Python 3.11+: fromisoformat가 TZ를 해석
            dt = datetime.fromisoformat(s)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
        except Exception:
            print(f"[WARNING] Invalid datetime ISO format: {s}")
            return None

    start = _parse_iso(start_raw) if start_raw else None
    end = _parse_iso(end_raw) if end_raw else None

    comp = ProposerWeeklyLevelComputer(window_start=start, window_end=end)
    res = comp.run(only_proposer_ids=ids)

    total_rows = sum(res.values())
    total_users = len(res)
    print(f"[compute_proposer_levels] users={total_users}, updated_rows={total_rows}")

    return res