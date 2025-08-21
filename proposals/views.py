import json
from typing import Any, Dict

from django.db.models import Count, Max, F, Q
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView


from .models import Proposal
from django.utils.decorators import method_decorator
from utils.choices import IndustryChoices, ZoomChoices
from .serializers import (
    ProposalCreateSerializer,
    ProposalMapItemSerializer,
    ProposalDetailSerializer,
    ProposalMyCreatedItemSerializer
)


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

        # ✅ QueryDict를 일반 dict로 재구성 (여기서 JSON 문자열을 파싱)
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

        sido = request.query_params.get("sido")
        sigungu = request.query_params.get("sigungu")
        eupmyundong = request.query_params.get("eupmyundong")

        if sido and sigungu and eupmyundong:
            return self._dong_detail_list(request, sido, sigungu, eupmyundong)
        return self._cluster_counts(sido, sigungu)

    def _cluster_counts(self, sido: str | None, sigungu: str | None):
        # 그룹필드/베이스쿼리
        if not sido and not sigungu:
            group = "address__sido"
            base = Proposal.objects.all()
        elif sido and not sigungu:
            group = "address__sigungu"
            base = Proposal.objects.filter(address__sido=sido)
        else:
            group = "address__eupmyundong"
            base = Proposal.objects.filter(address__sido=sido, address__sigungu=sigungu)

        # 그룹화(빈값/NULL 제외) + 개수 + 샘플 id
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
            pos_json = pos_map.get(g["sample_id"], {})
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
            .annotate(
                likes_count=Count("proposer_like_proposal", distinct=True),
                proposer_scraps=Count("proposer_scrap_proposal", distinct=True),
                founder_scraps=Count("founder_scrap_proposal", distinct=True),
            )
            .annotate(
                # 정렬용(명세에만 필요): 동일 동에서의 작성자 레벨 최대/최신 중 선택 가능
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

        # 업종 필터
        industry = request.query_params.get("industry")
        if industry:
            valid = {c for c, _ in IndustryChoices.choices}
            if industry not in valid:
                return Response({"detail": "Invalid industry choice."}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(industry=industry)

        # 정렬: 기본 '인기순'
        order = request.query_params.get("order", "인기순")
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