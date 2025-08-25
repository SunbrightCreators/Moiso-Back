from __future__ import annotations
import logging
from accounts.services import ProposerWeeklyLevelComputer

logger = logging.getLogger("accounts.crons")

def compute_proposer_levels() -> dict[str, int]:
    """
    매개변수 없이 호출되며, 내부적으로 최근 7일 윈도우로 계산합니다.
    Returns:
        {proposer_id: updated_rows_count}
    """
    comp = ProposerWeeklyLevelComputer()  # 최근 7일 윈도우 자동
    res = comp.run()
    total_rows = sum(res.values())
    total_users = len(res)
    logger.info("[compute_proposer_levels] users=%s, updated_rows=%s", total_users, total_rows)
    return res

