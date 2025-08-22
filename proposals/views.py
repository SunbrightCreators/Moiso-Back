import json
from typing import Any, Dict
from django.db.models import Count, Max, F, Q
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.http import HttpRequest
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from utils.choices import ProfileChoices, IndustryChoices, ZoomChoices
from utils.decorators import validate_path_choices
from .models import Proposal
from .serializers import (
    ProposalCreateSerializer,
    ProposalMapItemSerializer,
    ProposalDetailSerializer,
    ProposalMyCreatedItemSerializer,
    ProposalIdSerializer
)
from .services import ProposerLikeProposalService, ProposerScrapProposalService, FounderScrapProposalService


def _clean(val):
    return val.strip() if isinstance(val, str) else val

def _maybe_json(val):
    val = _clean(val)
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val  # 파싱 실패 시 원문 유지
    return val


# ── POST /proposals : 제안글 추가 ─────────────────────────────────────────
class ProposalsRoot(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        user = request.user
        proposer = getattr(user, "proposer", None)
        if proposer is None:
            return Response(
                {"detail": "proposer 프로필이 존재하지 않습니다. 먼저 생성하세요."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if "image" in request.data and not request.FILES.getlist("image"):
            return Response(
                {"image": ["The submitted data was not a file. Check the encoding type on the form."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        files = request.FILES.getlist("image")
        if len(files) > 3:
            return Response(
                {"image": [f"최대 3개까지 업로드할 수 있습니다. (보낸 개수: {len(files)})"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # QueryDict를 일반 dict로 재구성 (JSON 문자열 파싱)
        payload = {
            "title":   _clean(request.data.get("title")),
            "content": _clean(request.data.get("content")),
            "industry": _clean(request.data.get("industry")),
            "business_hours": _maybe_json(request.data.get("business_hours")),
            "address":        _maybe_json(request.data.get("address")),
            "position":       _maybe_json(request.data.get("position")),
            "radius": _clean(request.data.get("radius")),
        }

        # radius 정수 변환(choices 매칭 위해)
        if payload["radius"] is not None:
            try:
                payload["radius"] = int(payload["radius"])
            except (TypeError, ValueError):
                pass

        serializer = ProposalCreateSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        proposal = Proposal.objects.create(
            user=proposer,
            title=v["title"],
            content=v["content"],
            industry=v["industry"],
            business_hours=v["business_hours"],
            address=v["address"],
            position=v["position"],
            radius=v["radius"],
        )

        if files:
            if len(files) >= 1: proposal.image1 = files[0]
            if len(files) >= 2: proposal.image2 = files[1]
            if len(files) >= 3: proposal.image3 = files[2]
            proposal.save(update_fields=["image1", "image2", "image3"])

        return Response({"detail": "제안글을 추가했어요."}, status=status.HTTP_201_CREATED)


# ── GET /proposals/{zoom} : 지도 조회(요약) ──────────────────────────────
class ProposalsZoom(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, zoom: int):
        valid_zooms = {c.value for c in ZoomChoices}
        if zoom not in valid_zooms:
            return Response(
                {"detail": "Invalid zoom. Use one of [0, 500, 2000, 10000]."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sido        = request.query_params.get("sido")
        sigungu     = request.query_params.get("sigungu")
        eupmyundong = request.query_params.get("eupmyundong")
        industry    = request.query_params.get("industry")

        # industry 유효성(클러스터/목록 공통)
        if industry:
            valid = {c for c, _ in IndustryChoices.choices}
            if industry not in valid:
                return Response({"detail": "Invalid industry choice."}, status=status.HTTP_400_BAD_REQUEST)

        # 0m: 동 이하 - 동 상세 목록 그대로 반환
        if zoom == 0:
            if not (sido and sigungu and eupmyundong):
                return Response(
                    {"detail": "sido, sigungu, eupmyundong 쿼리 파라미터가 모두 필요합니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # _dong_detail_list 내부에서 industry/order 처리
            return self._dong_detail_list(request, sido, sigungu, eupmyundong)

        # 500m: 동 클러스터 (sido, sigungu 필수)
        if zoom == 500:
            if not (sido and sigungu):
                return Response(
                    {"detail": "동 지도(500m)에는 sido와 sigungu가 필요합니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return self._cluster_counts(sido=sido, sigungu=sigungu, industry=industry)

        # 2km: 구 클러스터 (sido 필수)
        if zoom == 2000:
            if not sido:
                return Response(
                    {"detail": "구 지도(2km)에는 sido가 필요합니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return self._cluster_counts(sido=sido, sigungu=None, industry=industry)

        # 10km: 도 클러스터 (전국)
        return self._cluster_counts(sido=None, sigungu=None, industry=industry)

    def _cluster_counts(self, sido: str | None, sigungu: str | None, industry: str | None):
        """
        - sido/sigungu 조합에 따라 그룹 필드를 결정
        - industry가 있으면 해당 업종만 집계
        - 응답: [{id, address, position{lat,lng}, number}]
        """
        # 그룹/베이스쿼리 결정
        if not sido and not sigungu:
            group = "address__sido"
            base = Proposal.objects.all()
        elif sido and not sigungu:
            group = "address__sigungu"
            base = Proposal.objects.filter(address__sido=sido)
        else:
            group = "address__eupmyundong"
            base = Proposal.objects.filter(address__sido=sido, address__sigungu=sigungu)

        #수락된 제안글 지우기
        base = base.filter(funding__isnull=True)

        if industry:
            base = base.filter(industry=industry)

        # 빈값/NULL 제외 + 개수 + 샘플 id
        base = base.exclude(**{f"{group}__isnull": True}).exclude(**{group: ""})
        grouped = (
            base.values(group)
                .annotate(number=Count("id"), sample_id=Max("id"))
                .order_by(group)
        )

        # 샘플 포지션 조회
        sample_ids = [g["sample_id"] for g in grouped if g["sample_id"]]
        pos_map = {
            row["id"]: (row.get("position") or {})
            for row in Proposal.objects.filter(id__in=sample_ids).values("id", "position")
        }

        data = []
        for idx, g in enumerate(grouped, start=1):
            name = g[group]
            if not name:
                continue
            pos_json = pos_map.get(g["sample_id"], {}) or {}
            data.append({
                "id": idx,
                "address": name,
                "position": {
                    "latitude":  pos_json.get("latitude"),
                    "longitude": pos_json.get("longitude"),
                },
                "number": g["number"],
            })

        return Response(data, status=status.HTTP_200_OK)

    def _dong_detail_list(self, request, sido: str, sigungu: str, eupmyundong: str):
        qs = (
            Proposal.objects
            .filter(
                address__sido=sido,
                address__sigungu=sigungu,
                address__eupmyundong=eupmyundong,
            )
            .filter(funding__isnull=True)
            .annotate(
                likes_count=Count("proposer_like_proposal", distinct=True),
                proposer_scraps=Count("proposer_scrap_proposal", distinct=True),
                founder_scraps=Count("founder_scrap_proposal", distinct=True),
            )
            .annotate(
                level_area=Max(
                    "user__proposer_level__level",
                    filter=Q(
                        user__proposer_level__address__sido=sido,
                        user__proposer_level__address__sigungu=sigungu,
                        user__proposer_level__address__eupmyundong=eupmyundong,
                    ),
                ),
                scraps_count=F("proposer_scraps") + F("founder_scraps"),
            )
        )

        # 업종 필터(선택)
        industry = request.query_params.get("industry")
        if industry:
            valid = {c for c, _ in IndustryChoices.choices}
            if industry not in valid:
                return Response({"detail": "Invalid industry choice."}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(industry=industry)


        order = request.query_params.get("order", "최신순")
        order_map = {
            "인기순": "-likes_count",
            "최신순": "-created_at",
            "레벨순": "-level_area",
        }
        if order not in order_map:
            return Response(
                {"detail": "Invalid order. Use one of ['인기순','최신순','레벨순']."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = qs.select_related("user__user").order_by(order_map[order], "-id")
        serializer = ProposalMapItemSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

# ── GET /proposals/{proposal_id}/{profile} : 상세 ────────────────────────
class ProposalsPk(APIView):
    """
    공개 엔드포인트 (인증 불필요)
    profile ∈ {'proposer','founder'}
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, proposal_id: int, profile: str):
        profile = (profile or "").lower()
        if profile not in ("proposer", "founder"):
            return Response(
                {"detail": "Invalid profile. Use one of ['proposer','founder']."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        proposal = get_object_or_404(
            Proposal.objects.select_related("user__user"),
            pk=proposal_id
        )

        serializer = ProposalDetailSerializer(
            proposal,
            context={"request": request, "profile": profile},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class ProposalsMyCreated(APIView):
    """
    GET /proposals/proposer/my-created?sido=...&sigungu=...&eupmyundong=...
    - 로그인한 '제안자(Proposer)'가 해당 동에서 작성한 제안글을 최신순으로 반환
    - 목록 카드 요약 필드만: id, created_at("YYYY.MM.DD."), title
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Proposer 검사
        proposer = getattr(request.user, "proposer", None)
        if proposer is None:
            return Response(
                {"detail": "proposer 프로필이 존재하지 않습니다. 먼저 생성하세요."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 필수 쿼리 파라미터
        sido        = request.query_params.get("sido")
        sigungu     = request.query_params.get("sigungu")
        eupmyundong = request.query_params.get("eupmyundong")
        if not (sido and sigungu and eupmyundong):
            return Response(
                {"detail": "sido, sigungu, eupmyundong 쿼리 파라미터가 모두 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = (
            Proposal.objects
            .filter(
                user=proposer,
                address__sido=sido,
                address__sigungu=sigungu,
                address__eupmyundong=eupmyundong,
            )
            .only("id", "title", "created_at")
            .order_by("-created_at", "-id")
        )
        data = ProposalMyCreatedItemSerializer(qs, many=True).data
        return Response(data, status=status.HTTP_200_OK)

class ProposerLike(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request:HttpRequest, format=None):
        serializer = ProposalIdSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        proposal_id = serializer.validated_data['proposal_id']

        service = ProposerLikeProposalService(request)
        is_created = service.post(proposal_id)

        if is_created:
            return Response(
                { 'detail': '이 제안을 좋아해요.' },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                { 'detail': '좋아요를 취소했어요.' },
                status=status.HTTP_200_OK,
            )

@method_decorator(validate_path_choices(profile=ProfileChoices.values), name='dispatch')
class ProfileScrap(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request:HttpRequest, profile, format=None):
        serializer = ProposalIdSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        proposal_id = serializer.validated_data['proposal_id']

        if profile == ProfileChoices.proposer.value:
            service = ProposerScrapProposalService(request)
        elif profile == ProfileChoices.founder.value:
            service = FounderScrapProposalService(request)
        is_created = service.post(proposal_id)

        if is_created:
            return Response(
                { 'detail': '이 제안을 스크랩했어요.' },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                { 'detail': '스크랩을 취소했어요.' },
                status=status.HTTP_200_OK,
            )

    def get(self, request:HttpRequest, profile, format=None):
        sido = request.query_params.get('sido')
        sigungu = request.query_params.get('sigungu')
        eupmyundong = request.query_params.get('eupmyundong')

        if profile == ProfileChoices.proposer.value:
            service = ProposerScrapProposalService(request)
        elif profile == ProfileChoices.founder.value:
            service = FounderScrapProposalService(request)
        data = service.get(sido, sigungu, eupmyundong)

        return Response(
            data,
            status=status.HTTP_200_OK,
        )
