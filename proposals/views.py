from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.http import HttpRequest
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from utils.choices import ProfileChoices, ZoomChoices
from utils.decorators import validate_path_choices
from maps.services import GeocodingService
from utils.helpers import resolve_viewer_addr
from .models import Proposal
from collections import OrderedDict
from .serializers import (
    ProposalCreateSerializer,
    ProposalListSerializer,
    ProposalDetailSerializer,
    ProposalMyCreatedItemSerializer,
    ProposalIdSerializer,
    ProposalZoomFounderItemSerializer
)
from .services import (
  ProposerLikeProposalService, 
  ProposerScrapProposalService, 
  FounderScrapProposalService,
  ProposalMapService
)


# ── POST /proposals : 제안글 추가 ─────────────────────────────────────────
class ProposalsRoot(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        files = request.FILES.getlist("image")
        if "image" in request.data and not files:
            return Response({"image": ["해당 데이터는 파일이 아닙니다. 파일 형식에 맞춰주세요."]},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(files) > 3:
            return Response({"image": [f"최대 3개까지 업로드할 수 있습니다. (보낸 개수: {len(files)})"]},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = ProposalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        proposer = getattr(request.user, "proposer", None)
        if proposer is None:
            return Response({"detail": "proposer 프로필이 존재하지 않습니다. 먼저 생성하세요."},
                            status=status.HTTP_403_FORBIDDEN)

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
@method_decorator(validate_path_choices(profile=ProfileChoices.values), name="dispatch")
class ProposalsZoom(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: HttpRequest, profile: str, zoom: int):
        ### 요청 수신 ###
        sido        = request.query_params.get("sido")
        sigungu     = request.query_params.get("sigungu")
        eupmyundong = request.query_params.get("eupmyundong")
        industry    = request.query_params.get("industry")
        order       = request.query_params.get("order", "최신순")
        
        ### 요청값 검증 ###
        if zoom not in ZoomChoices.values:
            return Response(
                {"detail": f"Invalid zoom. Use one of: {ZoomChoices.values}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if zoom == ZoomChoices.M2000 and not sido:
            return Response({"detail": "구 지도(2km)에는 sido가 필요합니다."},
                            status=status.HTTP_400_BAD_REQUEST)
        if zoom == ZoomChoices.M500 and not (sido and sigungu):
            return Response({"detail": "동 지도(500m)에는 sido와 sigungu가 필요합니다."},
                            status=status.HTTP_400_BAD_REQUEST)
        if zoom == ZoomChoices.M0 and not (sido and sigungu and eupmyundong):
            return Response({"detail": "sido, sigungu, eupmyundong 쿼리 파라미터가 모두 필요합니다."},
                            status=status.HTTP_400_BAD_REQUEST)

        # 서비스 호출
        svc = ProposalMapService(request, profile)

        # 동 이하(0): 목록 + is_liked/is_scrapped/is_address
        # 동 이하: 상세 목록
        if zoom == ZoomChoices.M0:
            try:
                qs = (
                    Proposal.objects
                    .filter_address(sido, sigungu, eupmyundong)
                    .filter(funding__isnull=True)
                    .with_analytics()
                    .with_level_area(sido=sido, sigungu=sigungu, eupmyundong=eupmyundong)
                    .filter_industry_choice(industry)
                    .with_user()
                    .with_has_funding()  # founder 응답에서 필요
                )
                viewer_addr = resolve_viewer_addr(request.user, profile)
                qs = qs.with_flags(user=request.user, profile=profile, viewer_addr=viewer_addr)
                qs = qs.order_by_choice(order)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            prof = (profile or "").lower()
            groups = OrderedDict()

            for obj in qs:
                pos = obj.position or {}
                lat = pos.get("latitude")
                lng = pos.get("longitude")
                key = (lat, lng)

                if key not in groups:
                    groups[key] = {
                        "position": {"latitude": lat, "longitude": lng},  # ← 그룹 바깥에만 position
                        "proposals": [],
                    }

                if prof == "founder":
                    item = ProposalZoomFounderItemSerializer(
                        obj, context={"request": request}
                    ).data
                else:  # proposer
                    # proposer도 아이템 내부에 position 없어야 하므로 ProposalListSerializer 사용
                    item = ProposalListSerializer(
                        obj, context={"request": request}
                    ).data

                groups[key]["proposals"].append(item)

            return Response(list(groups.values()), status=status.HTTP_200_OK)


        # 클러스터(시도/시군구/읍면동)
        if zoom == ZoomChoices.M10000:
            grouped = svc.cluster_counts_sido(industry)
        elif zoom == ZoomChoices.M2000:
            grouped = svc.cluster_counts_sigungu(sido, industry)
        else:  # ZoomChoices.M500
            grouped = svc.cluster_counts_eupmyundong(sido, sigungu, industry)

        # 중심좌표(지오코딩) + is_address 가공은 뷰에서
        geocoder = GeocodingService(request)
        viewer_addr = resolve_viewer_addr(request.user, profile)

        def _match(viewer, *, sido=None, sigungu=None, eup=None) -> bool:
            if not viewer:
                return False
            def _one(a: dict) -> bool:
                if not isinstance(a, dict): return False
                if sido and a.get("sido") != sido: return False
                if sigungu is not None and a.get("sigungu") != sigungu: return False
                if eup is not None and a.get("eupmyundong") != eup: return False
                return True
            if isinstance(viewer, list):
                return any(_one(a) for a in viewer)
            if isinstance(viewer, dict):
                return _one(viewer)
            return False

        result = []
        for idx, row in enumerate(grouped, start=1):
            addr_text = row["address"]

            if zoom == ZoomChoices.M10000:
                full_addr = addr_text
                is_address = _match(viewer_addr, sido=addr_text)
            elif zoom == ZoomChoices.M2000:
                full_addr = f"{sido} {addr_text}"
                is_address = _match(viewer_addr, sido=sido, sigungu=addr_text)
            else:  # M500
                full_addr = f"{sido} {sigungu} {addr_text}"
                is_address = _match(viewer_addr, sido=sido, sigungu=sigungu, eup=addr_text)
            # position 반환
            try:
                pos = geocoder.get_address_to_position(query_address=full_addr)
            except Exception:
                pos = {"latitude": None, "longitude": None}

            result.append({
                "id": idx,
                "address": addr_text,
                "position": pos,
                "number": row["number"],
                "is_address": is_address,
            })

        ### 응답 송신 ###
        return Response(result, status=status.HTTP_200_OK)

# ── GET /proposals/{proposal_id}/{profile} : 상세 ────────────────────────
class ProposalsPk(APIView):
    """
    profile ∈ {'proposer','founder'}
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, proposal_id: int, profile: str):
        profile = (profile or "").lower()
        if profile not in ("proposer", "founder"):
            return Response(
                {"detail": "Invalid profile. Use one of ['proposer','founder']."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = (
            Proposal.objects
            .with_analytics()
            .with_user()  # select_related("user__user") 포함 역할
            .with_has_funding() 
        )
        viewer_addr = resolve_viewer_addr(request.user, profile)
        qs = qs.with_flags(user=request.user, profile=profile, viewer_addr=viewer_addr)

        proposal = get_object_or_404(qs, pk=proposal_id)
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
