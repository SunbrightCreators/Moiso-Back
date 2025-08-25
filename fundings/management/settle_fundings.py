from __future__ import annotations
from datetime import datetime
from fundings.services import FundingSettlementService

def settle_fundings(now: datetime | None = None, verbose: bool = True):
    """
    마감된(IN_PROGRESS) 펀딩을 성공/실패로 정산합니다.
    기존 management command의 handle()을 일반 함수로 치환한 버전입니다.

    Args:
        now: 기준 시각(없으면 timezone.now())
        verbose: True면 요약 로그를 print

    Returns:
        FundingSettlementResult  (updated/succeeded/failed/skipped 필드 포함)
    """
    svc = FundingSettlementService(now=now)
    result = svc.run()

    if verbose:
        print(
            f"settled: {result.updated} "
            f"(succeeded={result.succeeded}, failed={result.failed}, skipped={result.skipped})"
        )
    return result
