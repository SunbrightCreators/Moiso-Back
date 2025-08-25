from __future__ import annotations
from accounts.services import ProposerWeeklyLevelComputer

def compute_proposer_levels() -> dict[str, int]:
    """
    매개변수 없이 호출되며, 내부적으로 최근 7일 윈도우로 계산합니다.
    Returns:
        {proposer_id: updated_rows_count}
    """
    comp = ProposerWeeklyLevelComputer()  # window=None -> 최근 7일 자동
    res = comp.run()  # 전체 대상
    try:
        total_rows = sum(res.values())
        total_users = len(res)
        print(f"[compute_proposer_levels] users={total_users}, updated_rows={total_rows}")
    except Exception:
        pass
    return res

