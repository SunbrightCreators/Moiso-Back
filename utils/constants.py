from enum import Enum

class CacheKey(Enum):
    """
    애플리케이션에서 사용하는 캐시키를 정의하는 ENUM 클래스
    """
    PROPOSAL_VECTOR = 'proposal_vector:{proposal_id}'
    RECOMMENDED_PROPOSALS = 'recommended_proposals:{profile}:{user_id}'

    def format(self, **kwargs):
        return self.value.format(**kwargs)
