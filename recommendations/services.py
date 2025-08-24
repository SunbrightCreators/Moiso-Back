import re
import numpy as np
from django.http import HttpRequest
from rest_framework.exceptions import ValidationError, NotFound, APIException
from konlpy.tag import Okt
from gensim.models import KeyedVectors
from sklearn.metrics.pairwise import cosine_similarity
from utils.choices import ProfileChoices
from utils.decorators import require_profile
from proposals.models import Proposal
from proposals.serializers import ProposalListSerializer

okt = Okt()
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
    word2vec_model = KeyedVectors.load_word2vec_format('recommendations/GoogleNews-vectors-negative300.bin', binary=True)
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
        text = re.sub('[^가-힣\s]', '', text)
        # 명사 추출
        tokens = okt.nouns(text)
        # 불용어 제거
        filtered_tokens = [word for word in tokens if word not in korean_stopwords and len(word) > 1]
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

    def calc_cosine_similarity(self, source_vector, comparison_vectors):
        """
        소스 벡터와 모든 게시물 벡터 간의 유사도를 계산합니다.
        """
        # 벡터들을 2D 배열로 변환 (scikit-learn의 입력 형식)
        source_vector = source_vector.reshape(1, -1)
        comparison_vectors = np.array(comparison_vectors)
        # 코사인 유사도 계산
        similarity_scores = cosine_similarity(source_vector, comparison_vectors)
        return similarity_scores[0]

class RecommendationScrapService:
    def __init__(self, request:HttpRequest):
        self.request = request

        if not word2vec_model:
            raise APIException('AI 모델을 불러오지 못했어요. 관리자에게 문의하세요.')
        self.ai = AI(word2vec_model)

    @require_profile(ProfileChoices.founder)
    def recommend_founder_scrap_proposal(self):
        # 사용자가 스크랩한 최신 제안 10개 가져오기
        scrapped_proposals = Proposal.objects.filter(
            founder_scrap_proposal__user=self.request.user,
        ).order_by(
            '-created_at',
        )[:10]
        if not scrapped_proposals:
            raise NotFound('스크랩한 제안이 없어요.')

        valid_scrapped_proposals_vectors = list()
        for proposal in scrapped_proposals:
            # 각 제안 벡터 계산
            vector = self.ai.vectorize(proposal.title + proposal.content)
            # 유효한 벡터만 필터링
            if vector is not None:
                valid_scrapped_proposals_vectors.append(vector)
        if not valid_scrapped_proposals_vectors:
            raise ValidationError('스크랩한 제안의 내용이 유효하지 않아요.')

        # 모든 유효한 벡터를 평균하여 대표 벡터 생성
        source_vector = np.mean(valid_scrapped_proposals_vectors, axis=0)

        # 스크랩한 제안 제외 + 업종 필터링
        proposals = Proposal.objects.exclude(
            founder_scrap_proposal__user=self.request.user,
        ).filter_user_industry(
            self.request.user,
            ProfileChoices.founder.value,
        )

        ### 캐싱 필요 ###
        valid_proposals_and_vectors = list()
        for proposal in proposals:
            # 각 제안 벡터 계산
            vector = self.ai.vectorize(proposal.title + proposal.content)
            # 유효한 벡터만 필터링
            if vector is not None:
                valid_proposals_and_vectors.append((proposal, vector))

        # 코사인 유사도 계산
        similarity_scores = self.ai.calc_cosine_similarity(
            source_vector=source_vector,
            comparison_vectors=[vector for proposal, vector in valid_proposals_and_vectors],
        )

        # 유사도 점수 기반 추천 목록 정렬
        recommended_proposals_with_scores = sorted(
            zip(valid_proposals_and_vectors, similarity_scores),
            key=lambda x: x[1],
            reverse=True,
        )

        top_recommended_proposals = [proposal for (proposal, vector), score in recommended_proposals_with_scores][:3]
        serializer = ProposalListSerializer(top_recommended_proposals, many=True)
        return serializer.data

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
