import re
import numpy as np
from konlpy.tag import Okt
from gensim.models import KeyedVectors
from sklearn.metrics.pairwise import cosine_similarity

okt = Okt()
model = KeyedVectors.load_word2vec_format('recommendations/GoogleNews-vectors-negative300.bin', binary=True)
korean_stopwords = [
    # 조사
    '은', '는', '이', '가', '을', '를', '에', '의', '와', '과', '도', '만', '부터', '까지',
    '로', '으로', '에서', '에게', '한테', '께서', '에게서', '한테서', '께', '이나', '나',
    '마저', '조차', '뿐', '밖에', '서부터', '부터', '까지', '마다', '씩', '이든지', '든지',
    '이든가', '든가', '라도', '라든지', '이나마', '나마', '이라도', '라도',
    # 어미
    '다', '야', '라', '죠', '네', '요', '아', '어', '여', '지', '더', '게', '니다',
    '습니다', '어요', '아요', '여요', '해요', '세요', '지요', '죠', '군요', '네요',
    '구나', '구먼', '거든', '거든요', '는데', '은데', '인데', '는지', '은지', '인지',
    '는가', '은가', '인가', '나요', '까요', '을까요', '를까요', '일까요',
    # 의존명사
    '것', '수', '때', '곳', '것들', '점', '바', '측면', '경우', '때문', '문제', '결과',
    '이유', '원인', '방법', '방식', '과정', '상황', '상태', '모습', '형태', '종류',
    '분야', '영역', '부분', '전체', '일부', '대부분', '나머지', '차이', '관계', '연관',
    # 대명사
    '그', '저', '이것', '그것', '저것', '이곳', '그곳', '저곳', '여기', '거기', '저기',
    '이렇게', '그렇게', '저렇게', '이런', '그런', '저런', '이러한', '그러한', '저러한',
    '누구', '무엇', '어디', '언제', '어떻게', '왜', '얼마나',
    # 보조용언
    '하다', '되다', '이다', '아니다', '있다', '없다', '같다', '다르다', '많다', '적다',
    '크다', '작다', '좋다', '나쁘다', '새롭다', '오래되다', '높다', '낮다', '빠르다', '느리다',
    # 부사
    '더', '덜', '가장', '매우', '너무', '아주', '정말', '진짜', '참', '꽤', '상당히',
    '조금', '약간', '살짝', '좀', '잠시', '잠깐', '계속', '항상', '늘', '자주',
    '가끔', '때때로', '이미', '벌써', '아직', '아직도', '이제', '지금', '현재',
    # 접속사
    '그리고', '그런데', '하지만', '그러나', '또한', '또', '및', '이며', '그래서',
    '따라서', '즉', '다시말해', '예를들어', '만약', '만일', '그러면', '그럼',
    # 감탄사
    '아', '어', '오', '우', '음', '어머', '아이고', '이런', '저런',
    # 기타 자주 나오는 무의미한 단어들
    '들', '등', '중', '전', '후', '위', '아래', '앞', '뒤', '안', '밖', '내', '외',
    '간', '사이', '동안', '통해', '따라', '위해', '대해', '관해', '대한', '관한',
    '한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉', '열',
    '첫', '둘째', '셋째', '넷째', '다섯째', '마지막'
]

class AI:
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
        vectors = [model[word] for word in tokens if word in model.key_to_index]
        if not vectors:
            return None
        # 단어 벡터들의 평균을 게시물 벡터로 사용
        return sum(vectors) / len(vectors)

    def calc_cosine_similarity(self, source_vector, all_vectors):
        """
        소스 벡터와 모든 게시물 벡터 간의 유사도를 계산합니다.
        """
        # 벡터들을 2D 배열로 변환 (scikit-learn의 입력 형식)
        source_vector = source_vector.reshape(1, -1)
        all_vectors = np.array(all_vectors)
        # 코사인 유사도 계산
        similarity_scores = cosine_similarity(source_vector, all_vectors)
        return similarity_scores[0]

class RecommendationCalcService:
    def _calc_level(self):
        pass

    def _calc_likes_ratio(self):
        pass

    def _calc_business_hours(self):
        pass

    def calc_score(self):
        pass
