import logging
logger = logging.getLogger("accounts.crons")
from accounts.management.compute_proposer_levels import compute_proposer_levels

def compute_levels_job():
    logger.info("compute_levels_job: 시작")
    res = compute_proposer_levels()
    logger.info(f"compute_levels_job: 완료 - users={len(res)}, updated={sum(res.values())}")