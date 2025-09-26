import os
from typing import Literal, Optional, Dict, Any, Set, List
import heapq
import re
import numpy as np
from dataclasses import dataclass
from django.conf import settings
from django.core.cache import cache
from django.db.models import Case, Count, OuterRef, Q, Subquery, Value, When, BooleanField, IntegerField
from django.db.models.functions import Coalesce
from django.http import HttpRequest
from rest_framework.exceptions import ValidationError, NotFound, APIException, PermissionDenied
from kiwipiepy import Kiwi
import fasttext
from sklearn.metrics.pairwise import cosine_similarity
from utils.choices import ProfileChoices, FounderTargetChoices
from utils.constants import CacheKey
from utils.decorators.service import require_profile
from utils.times import _parse_hhmm, _minutes_between, _overlap_minutes
from accounts.models import ProposerLevel
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

# ---- FastText lazy loader (환경변수 경로만 읽음) ----
FASTTEXT_MODEL_PATH = os.getenv("FASTTEXT_MODEL_PATH")
_fasttext_model = None

def get_fasttext_model():
    """
    호스트에 놓여 있는 FastText .bin을 1회 로드해 재사용.
    컨테이너 재시작/재생성에도 바인드 마운트만 유지되면 재다운로드 없음.
    """
    global _fasttext_model
    if _fasttext_model is not None:
        return _fasttext_model

    if not FASTTEXT_MODEL_PATH:
        raise APIException("FASTTEXT_MODEL_PATH가 설정되지 않았어요.")
    if not os.path.exists(FASTTEXT_MODEL_PATH):
        raise APIException(f"모델 파일이 없어요: {FASTTEXT_MODEL_PATH}")

    try:
        _fasttext_model = fasttext.load_model(FASTTEXT_MODEL_PATH)
        return _fasttext_model
    except Exception as e:
        raise APIException(f"AI 모델 로드 실패: {e}")

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
        내용을 FastText 벡터로 변환합니다.
        """
        tokens = self._preprocess_and_tokenize(text)

        # 토큰화된 단어들 중 모델에 존재하는 단어만 추출
        vectors = [self.model.get_word_vector(word) for word in tokens]
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

        return [item.id for score, item in sorted(min_heap, reverse=True)]

class RecommendationScrapService:
    def __init__(self, request:HttpRequest):
        self.request = request

        model = get_fasttext_model()
        self.ai = AI(model)
    
    def _cache_key_proposal(self, proposal_id):
        return CacheKey.PROPOSAL_VECTOR.format(proposal_id=proposal_id)

    def _calc_vectors(self, cache_key_method, posts, option:Literal['vector']|None=None):
        valid_vectors = list()
        for post in posts:
            vector = cache.get(cache_key_method(post.id))
            if vector is None: # 캐시가 없거나 유효한 벡터가 아닐 때
                vector = self.ai.vectorize(' '.join([post.title, post.content])) # 게시물 벡터 계산
                cache.set(cache_key_method(post.id), vector, timeout=365*24*60*60*1) # 수정 불가능하여 데이터가 변경되는 경우가 없으므로 1년 캐싱
            if vector is not None: # 캐시 또는 새로 계산한 값이 유효한 벡터일 때
                valid_vectors.append(vector if option == 'vector' else (post, vector))
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
            | Q(funding__isnull=False)
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
        top_recommended_proposal_id_list = self.ai.find_top_similar(
            source_vector=source_vector,
            items_and_vectors=valid_proposals_and_vectors,
        )

        top_recommended_proposals = Proposal.objects.filter(
            id__in=top_recommended_proposal_id_list
        ).annotate(
            similarity_order=Case(
                *[When(id=pk, then=Value(pos)) for pos, pk in enumerate(top_recommended_proposal_id_list)],
                output_field=IntegerField()
            )
        ).order_by(
            'similarity_order'
        ).with_analytics(
        ).with_user(
        ).with_flags(
            user=self.request.user,
            profile=ProfileChoices.founder.value
        )

        serializer = ProposalListSerializer(
            top_recommended_proposals,
            context={"request": self.request, "profile": ProfileChoices.founder.value},
            many=True
        )
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
    """
    Founder 전용: 단순 계산식 기반 제안글 추천
      - Level (40): 해당 제안글 '동'에서의 제안자 레벨(1/2/3 → 33/67/100로 정규화 후 가중)
      - Likes ratio (40): founder.target(local/stranger)에 맞춘 비율 가중
      - Business hours (20): 겹치는 시간 / 두 사람 중 더 긴 시간
    필터:
      - funding__isnull=True (펀딩 없는 제안만)
      - 주소: Founder가 선택한 '1개 동' (쿼리 or founder address 기본값)
      - 업종: Proposal.industry ∈ Founder.industry(최대 3개)
    정렬:
      - score desc, likes_count desc, id desc
    """
    def __init__(self, request: HttpRequest):
        self.request = request
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            raise PermissionDenied("로그인이 필요해요.")
        if not hasattr(user, "founder"):
            raise PermissionDenied("창업자 프로필이 필요해요.")

        self.user = user
        self.founder = user.founder

        # Founder 개인화 속성
        self.founder_addresses = getattr(self.founder, "address", None) or []
        self.founder_industries: Set[str] = set(getattr(self.founder, "industry", []) or [])
        self.founder_targets: Set[str] = set(getattr(self.founder, "target", []) or [])
        self.founder_hours: Dict[str, str] = getattr(self.founder, "business_hours", {}) or {}
        if not self.founder_addresses:
            raise PermissionDenied("추천을 위해 founder의 우리동네(최대 2개) 설정이 필요해요.")
        if not self.founder_industries:
            # 명세: 제안글 업종이 founder 관심업종에 포함되어야 함 → 관심업종 없으면 추천 불가
            raise PermissionDenied("추천을 위해 founder의 관심 업종 설정이 필요해요.")
        

    # -------------------------------
    # Address resolve (1개 동 필수)
    # -------------------------------
    def _resolve_address(self, sido: Optional[str], sigungu: Optional[str], eupmyundong: Optional[str]) -> Dict[str, str]:
        # 1) 쿼리 파라미터가 모두 오면 그것을 사용
        if all([sido, sigungu, eupmyundong]):
            return {"sido": sido, "sigungu": sigungu, "eupmyundong": eupmyundong}

        # 2) Founder 저장 주소(최대 2개)에서 첫 번째를 기본값으로
        #    - 리스트/튜플/단일 dict 모두 방어
        if isinstance(self.founder_addresses, list) and self.founder_addresses:
            a0 = self.founder_addresses[0]
            return {
                "sido": a0.get("sido"),
                "sigungu": a0.get("sigungu"),
                "eupmyundong": a0.get("eupmyundong"),
            }
        if isinstance(self.founder_addresses, dict):
            return {
                "sido": self.founder_addresses.get("sido"),
                "sigungu": self.founder_addresses.get("sigungu"),
                "eupmyundong": self.founder_addresses.get("eupmyundong"),
            }

        # 3) 그래도 없으면 권한 에러
        raise PermissionDenied("추천을 위해 우리동네(동) 설정이 필요해요.")

    # -------------------------------
    # Component scorers - 점수 컴포넌트 계산
    # -------------------------------
    @staticmethod
    def _norm_level_to_pct(level_val: Optional[int]) -> int:
        return {1: 33, 2: 67, 3: 100}.get(int(level_val or 0), 0)

    def _score_business_hours(self, proposal: Proposal) -> int:
        ps = proposal.business_hours or {}
        fs = self.founder_hours or {}

        p_start = _parse_hhmm(ps.get("start")); p_end = _parse_hhmm(ps.get("end"))
        f_start = _parse_hhmm(fs.get("start")); f_end = _parse_hhmm(fs.get("end"))
        if not (p_start and p_end and f_start and f_end):
            return 0

        p_len = _minutes_between(p_start, p_end)
        f_len = _minutes_between(f_start, f_end)
        if p_len <= 0 or f_len <= 0:
            return 0

        overlap = _overlap_minutes(p_start, p_end, f_start, f_end)
        base = max(p_len, f_len)  # ← 긴 쪽 기준
        return 100 if overlap >= 0.5 * base else 0

    def _likes_component_from_annot(self, p: Proposal) -> int:
        total = getattr(p, "total_likes", 0) or 0
        if total <= 0:
            return 0
        local = getattr(p, "local_likes", 0) or 0
        local_ratio = max(min(local / total, 1), 0)

        t = self.founder_targets
        if t == {FounderTargetChoices.LOCAL}:
            base = local_ratio
        elif t == {FounderTargetChoices.STRANGER}:
            base = 1 - local_ratio
        else:
            base = max(local_ratio, 1 - local_ratio)
        return int(round(base * 100))

    def recommend_calc(self, *, limit: Optional[int] = 10) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit or 10), 50))

        # 1) 주소 필터: 쿼리가 3개 다 오면 단일 동, 아니면 founder의 주소들(최대 2개) OR
        q_sido = getattr(self.request, "GET", {}).get("sido")
        q_sigungu = getattr(self.request, "GET", {}).get("sigungu")
        q_eup = getattr(self.request, "GET", {}).get("eupmyundong")

        # Founder 주소들(or 조건)로 후보군 필터
        addr_q = Q()
        if q_sido and q_sigungu and q_eup:
            # 단일 동 선택(옵션)
            addr_q = Q(
                address__sido=q_sido,
                address__sigungu=q_sigungu,
                address__eupmyundong=q_eup,
            )
        else:
            # 창업자가 가진 주소들 전체(OR) – 최대 2개
            for a in (self.founder_addresses or [])[:2]:
                s, g, e = a.get("sido"), a.get("sigungu"), a.get("eupmyundong")
                if s and g and e:
                    addr_q |= Q(address__sido=s, address__sigungu=g, address__eupmyundong=e)

        if not addr_q:
            raise PermissionDenied("추천을 위해 founder의 우리동네(동) 정보가 필요해요.")

        # 레벨 Subquery: "해당 제안글의 동"에서의 작성자(Proposer) 레벨
        level_subq = ProposerLevel.objects.filter(
        user=OuterRef("user"),
        address__sido=OuterRef("address__sido"),
        address__sigungu=OuterRef("address__sigungu"),
        address__eupmyundong=OuterRef("address__eupmyundong"),
        ).order_by("-id").values("level")[:1]
        

        qs = (
            Proposal.objects
            .filter(funding__isnull=True)
            .filter(addr_q)
            .filter(industry__in=list(self.founder_industries))
            .select_related("user", "user__user")     # ← obj.user.user 접근 대비 (N+1 방지)
        )

        # 1) 항상 존재해야 하는 필드들을 기본값/집계로 채움
        qs = qs.annotate(
            # 제안자의 '해당 동' 레벨
            proposer_level_at_addr=Coalesce(Subquery(level_subq, output_field=IntegerField()), 0),

            # 좋아요/스크랩 집계
            likes_count=Coalesce(Count("proposer_like_proposal__user", distinct=True), 0),
            scraps_count=Coalesce(Count("founder_scrap_proposal__user", distinct=True), 0),

            # founder가 이 제안을 스크랩했는지
            _my_scrap=Count(
                "founder_scrap_proposal__user",
                filter=Q(founder_scrap_proposal__user=self.user.founder),
                distinct=True,
            ),
        ).annotate(
            is_scrapped=Case(
                When(_my_scrap__gt=0, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),

            # founder 응답에서는 좋아요 불가 → False 고정(Detail/MapItem에서 founder면 어차피 pop될 수도 있음)
            is_liked=Value(False, output_field=BooleanField()),

            # 주소 필터로 이미 founder 우리동네만 옴 → True 고정
            is_address=Value(True, output_field=BooleanField()),

            # Detail/ZoomFounder가 요구
            has_funding=Value(False, output_field=BooleanField()),
        )

        # (필요하면) with_analytics/with_user가 있으면 덮어쓰기
        try:
            qs = qs.with_analytics()
            
        except Exception:
            pass
        try:
            try:
                qs = qs.with_user(self.user)
            except TypeError:
                qs = qs.with_user()
        except Exception:
            pass

        # 정렬/슬라이스는 기존 로직 유지
        candidates = list(qs.order_by("-likes_count", "-created_at", "-id")[:200])





        @dataclass
        class CalcWeights:
            level: int = 40
            likes_ratio: int = 40
            business_hours: int = 20

        CALC_WEIGHTS = CalcWeights()

        w = CALC_WEIGHTS
        denom = (w.level + w.likes_ratio + w.business_hours)
        rows: List[Dict[str, Any]] = []
        for p in candidates:
            level_pct = self._norm_level_to_pct(getattr(p, "proposer_level_at_addr", 0))
            likes_pct = self._likes_component_from_annot(p)
            hours_pct = self._score_business_hours(p)

            total = (
                (level_pct * w.level) +
                (likes_pct * w.likes_ratio) +
                (hours_pct * w.business_hours)
            ) / denom
            score = int(round(total))

            if score >= 60:  # 명세 컷 유지
                rows.append({"proposal": p, "score": score})

        # 정렬: score desc, likes_count desc, id desc
        rows.sort(key=lambda x: (x["score"], getattr(x["proposal"], "likes_count", 0), x["proposal"].id), reverse=True)
        top = rows[:limit]

        # 2) 직렬화 (score/components 주입하지 않음)
        ser = ProposalListSerializer(
            [r["proposal"] for r in top],
            many=True,
            context={"request": self.request, "profile": ProfileChoices.founder.value},
        ).data
        return ser  # ← 점수 미노출