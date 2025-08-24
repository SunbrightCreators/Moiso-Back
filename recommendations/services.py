import os
from typing import Literal
import heapq
import re
import numpy as np
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpRequest
from rest_framework.exceptions import ValidationError, NotFound, APIException
from kiwipiepy import Kiwi
from gensim.models import KeyedVectors
from sklearn.metrics.pairwise import cosine_similarity
from utils.choices import ProfileChoices
from utils.constants import CacheKey
from utils.decorators import require_profile
from proposals.models import Proposal
from proposals.serializers import ProposalListSerializer

kiwi = Kiwi()
korean_stopwords = [
    # 의미 없는 의존명사 및 단위
    '것', '수', '때', '곳', '점', '바', '위', '아래', '중', '등', '등등', '전', '후', 
    '내', '외', '말', '개', '분', '개인', '가지', '분', '건', '일', '이',
    # 자주 나오는 추상적 개념 및 대명사
    '부분', '전체', '문제', '방법', '이유', '원인', '결과', '과정', '상황', '상태', 
    '모습', '경우', '측면', '관계', '대한', '관한', '대해', '관해', '대부분', '동안',
    # 지칭 대명사 및 지시어
    '이것', '그것', '저것', '이곳', '그곳', '저곳', '여기', '거기', '저기',
    # 불필요한 숫자
    '한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉', '열',
    # 기타 자주 사용되는 불용어
    '나', '저', '저희', '우리', '자신', '누구', '무엇', '어디', '언제', '어떻게', '왜', 
    '하나', '둘', '셋', '넷', '다섯'
]

try:
    model_path = os.path.join(settings.BASE_DIR, 'recommendations', 'GoogleNews-vectors-negative300.bin')
    word2vec_model = KeyedVectors.load_word2vec_format(model_path, binary=True)
except Exception as e:
    print(f"Word2Vec 모델 로드 실패: {e}")
    word2vec_model = None

class AI:
    def __init__(self, model):
        self.model = model

    def _preprocess_and_tokenize(self, text:str):
        """
        한국어 텍스트를 전처리하고 명사만 추출하여 토큰화합니다.
        """
        # 한글과 띄어쓰기 외 모든 문자 제거
        text = re.sub(r'[^가-힣\s]', '', text)
        # 명사 추출
        tokens = kiwi.tokenize(text)
        # 불용어 제거
        filtered_tokens = list()
        for token in tokens:
            if ((token.tag.startswith('N'))
                and (len(token.form) > 1)
                and (token.form not in korean_stopwords)):
                filtered_tokens.append(token.form)

        return filtered_tokens

    def vectorize(self, text:str):
        """
        내용을 Word2Vec 벡터로 변환합니다.
        """
        tokens = self._preprocess_and_tokenize(text)

        # 토큰화된 단어들 중 모델에 존재하는 단어만 추출
        vectors = [self.model[word] for word in tokens if word in self.model]
        if not vectors:
            return None

        # 단어 벡터들의 평균을 게시물 벡터로 사용
        return np.mean(vectors, axis=0)

    def find_top_similar(self, source_vector, items_and_vectors:list[tuple], top_k:int=3):
        min_heap = list()

        for item, vector in items_and_vectors:
            similarity = cosine_similarity(
                source_vector.reshape(1, -1),
                vector.reshape(1, -1),
            )[0][0]

            if len(min_heap) < top_k:
                heapq.heappush(min_heap, (similarity, item))
            elif similarity > min_heap[0][0]:
                heapq.heapreplace(min_heap, (similarity, item))

        return [item for score, item in sorted(min_heap, reverse=True)]

class RecommendationScrapService:
    def __init__(self, request:HttpRequest):
        self.request = request

        if not word2vec_model:
            raise APIException('AI 모델을 불러오지 못했어요. 관리자에게 문의하세요.')
        self.ai = AI(word2vec_model)
    
    def _cache_key_proposal(self, proposal_id):
        return CacheKey.PROPOSAL_VECTOR.format(proposal_id=proposal_id)

    def _calc_vectors(self, cache_key_method, posts, option:Literal['vector']|None=None):
        valid_vectors = list()
        for post in posts:
            vector = cache.get(cache_key_method(post.id))
            if not vector:
                # 각 게시물 벡터 계산
                vector = self.ai.vectorize(post.title + post.content)
                cache.set(cache_key_method(post.id), vector, timeout=365*24*60*60*1) # 수정 불가능하여 데이터가 변경되는 경우가 없으므로 1년 캐싱
            # 유효한 벡터만 필터링
            if vector is not None:
                if option == 'vector':
                    valid_vectors.append(vector)
                else:
                    valid_vectors.append((post, vector))
        return valid_vectors

    @require_profile(ProfileChoices.founder)
    def recommend_founder_scrap_proposal(self):
        cached_result = cache.get(CacheKey.RECOMMENDED_PROPOSALS.format(
            profile=ProfileChoices.founder.value,
            user_id=self.request.user.id,
        ))
        if cached_result:
            return cached_result

        # 사용자가 스크랩한 최신 제안 10개 가져오기
        scrapped_proposals = Proposal.objects.filter(
            founder_scrap_proposal__user=self.request.user.founder,
        ).order_by(
            '-created_at',
        )[:10]
        if not scrapped_proposals:
            raise NotFound('스크랩한 제안이 없어요.')

        # 스크랩한 제안 벡터 계산하기
        valid_scrapped_proposals_vectors = self._calc_vectors(
            cache_key_method=self._cache_key_proposal,
            posts=scrapped_proposals,
            option='vector',
        )
        if not valid_scrapped_proposals_vectors:
            raise ValidationError('스크랩한 제안의 내용이 유효하지 않아요.')

        # 모든 유효한 벡터를 평균하여 대표 벡터 생성
        source_vector = np.mean(valid_scrapped_proposals_vectors, axis=0)

        # 스크랩한 제안 또는 펀딩 있는 제안 제외 + 업종 필터링
        proposals = Proposal.objects.exclude(
            Q(founder_scrap_proposal__user=self.request.user.founder)
            | Q(funding__is_null=False)
        ).filter_user_industry(
            self.request.user,
            ProfileChoices.founder.value,
        )

        # 추천 후보군 제안 벡터 계산하기
        valid_proposals_and_vectors = self._calc_vectors(
            cache_key_method=self._cache_key_proposal,
            posts=proposals,
        )

        # 코사인 유사도 계산 및 유사도 상위 3개 제안 구하기
        top_recommended_proposals = self.ai.find_top_similar(
            source_vector=source_vector,
            items_and_vectors=valid_proposals_and_vectors,
        )

        serializer = ProposalListSerializer(top_recommended_proposals, many=True)
        result = serializer.data

        cache.set(
            CacheKey.RECOMMENDED_PROPOSALS.format(
                profile=ProfileChoices.founder.value,
                user_id=self.request.user.id,
            ),
            result,
            timeout=60*60*1, # 1시간 캐싱
        )
        return result

class RecommendationCalcService:
    def __init__(self, request:HttpRequest):
        self.request = request

    def _calc_level(self):
        pass

    def _calc_likes_ratio(self):
        pass

    def _calc_business_hours(self):
        pass

    def recommend_calc(self):
        pass
