from __future__ import annotations
import logging
logger = logging.getLogger("fundings.crons")
from fundings.management.settle_fundings import settle_fundings

def settle_fundings_job() -> None:
    """
    - 마감된(IN_PROGRESS) 펀딩을 SUCCEEDED/FAILED로 정산하고
      성공 시 구매 리워드를 발급합니다.
    """
    logger.info("settle_fundings_job: 시작")
    result = settle_fundings(verbose=False)
    logger.info(
        "settle_fundings_job: 완료 - "
        f"updated={result.updated}, succeeded={result.succeeded}, "
        f"failed={result.failed}, skipped={result.skipped}"
    )