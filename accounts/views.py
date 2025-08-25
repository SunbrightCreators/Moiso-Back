from datetime import datetime, timezone as dt_timezone
from django.db import transaction, IntegrityError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenRefreshSerializer as SJWTokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from django.utils.crypto import get_random_string

from maps.services import ReverseGeocodingService
from .models import (
    Proposer,
    Founder
)
from .serializers import (
    UserLoginSerializer,
    JwtRefreshRequestSerializer,
    ProposerSerializer,
    FounderSerializer,
    UserProposerSignupSerializer,
    UserFounderSignupSerializer,
    LocationHistoryCreateSerializer
)
from utils.choices import IndustryChoices, FounderTargetChoices, SexChoices


# ── Helpers ────────────────────────────────────────────────────────────────
def _labels_from_choices(choices_cls, codes):
    mapping = dict(choices_cls.choices)  # {value: label}
    if isinstance(codes, (list, tuple)):
        return [mapping.get(code, str(code)) for code in codes]
    return mapping.get(codes, str(codes))

def _user_base_payload(request, user):
    """기본 사용자 정보 JSON (라벨 변환 + 프로필 이미지 절대 URL)"""
    img_url = None

    # ImageField(FileField) 우선
    file_field = getattr(user, "profile_image", None)
    if file_field:
        try:
            rel_url = file_field.url  # 예: /media/...
        except Exception:
            rel_url = None
        if rel_url:
            img_url = request.build_absolute_uri(rel_url) if request else rel_url

    # (옵션) URLField를 쓰는 프로젝트 대비
    if not img_url:
        url_field = getattr(user, "profile_image_url", None)
        if url_field:
            img_url = url_field

    return {
        "email": user.email,
        "name": user.name,
        "birth": user.birth,
        "sex": _labels_from_choices(SexChoices, user.sex), 
        "profile_image": img_url,                         
        "is_marketing_allowed": user.is_marketing_allowed,
    }



# ── Views ──────────────────────────────────────────────────────────────────
class AccountsLoginRoot(APIView):
    """
    POST /accounts/login
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # JWT 발급
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        # 만료 시각 (exp → ISO8601 'Z')
        access_exp = datetime.fromtimestamp(access["exp"], tz=dt_timezone.utc)
        refresh_exp = datetime.fromtimestamp(refresh["exp"], tz=dt_timezone.utc)

        profiles = []
        if Proposer.objects.filter(user=user).exists():
            profiles.append("proposer")
        if Founder.objects.filter(user=user).exists():
            profiles.append("founder")

        body = {
            "grant_type": "Bearer",
            "access": {
                "token": str(access),
                "expire_at": access_exp.isoformat().replace("+00:00", "Z"),
            },
            "refresh": {
                "token": str(refresh),
                "expire_at": refresh_exp.isoformat().replace("+00:00", "Z"),
            },
            "profile": profiles,
        }
        return Response(body, status=status.HTTP_200_OK)


class AccountsAccessTokenRoot(APIView):
    """
    POST /accounts/access-token
    """
    permission_classes = [AllowAny]

    def post(self, request):
        req = JwtRefreshRequestSerializer(data=request.data)
        req.is_valid(raise_exception=True)

        refresh_str = req.validated_data["refresh_token"]

        sjw = SJWTokenRefreshSerializer(data={"refresh": refresh_str})
        sjw.is_valid(raise_exception=True)
        sjw_data = sjw.validated_data  # {'access': '...', ['refresh': '...']}

        access_str = sjw_data["access"]
        new_refresh_str = sjw_data.get("refresh", refresh_str)

        access_exp = datetime.fromtimestamp(
            AccessToken(access_str)["exp"], tz=dt_timezone.utc
        ).isoformat().replace("+00:00", "Z")

        refresh_exp = datetime.fromtimestamp(
            RefreshToken(new_refresh_str)["exp"], tz=dt_timezone.utc
        ).isoformat().replace("+00:00", "Z")

        body = {
            "grant_type": "Bearer",
            "access": {
                "token": access_str,
                "expire_at": access_exp,
            },
            "refresh": {
                "token": new_refresh_str,
                "expire_at": refresh_exp,
            },
        }
        return Response(body, status=status.HTTP_200_OK)


class AccountsRoot(APIView):
    """
    /accounts/
      - POST   : 회원가입 (Body로 프로필 자동판별: proposer_profile 또는 founder_profile)
      - DELETE : 로그인한 사용자 계정 삭제
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_authenticators(self):
        # GET/DELETE는 JWT 인증 적용, POST는 익명 허용
        if self.request and self.request.method in ("GET", "DELETE"):
            return [JWTAuthentication()]
        return super().get_authenticators()

    def get_permissions(self):
        if self.request and self.request.method in ("GET", "DELETE"):
            return [IsAuthenticated()]
        return [AllowAny()]
    
    # 회원 조회
    def get(self, request):
        user = request.user
        profiles = []
        if hasattr(user, "proposer"):
            profiles.append("proposer")
        if hasattr(user, "founder"):
            profiles.append("founder")

        return Response({"profile": profiles}, status=status.HTTP_200_OK)

    @transaction.atomic
    def post(self, request):
        data = request.data or {}

        has_proposer = "proposer_profile" in data
        has_founder = "founder_profile" in data

        if has_proposer and has_founder:
            return Response(
                {"detail": "proposer_profile 또는 founder_profile 중 하나만 보내주세요."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not has_proposer and not has_founder:
            profile_hint = (data.get("profile") or "").lower()
            if profile_hint not in ("proposer", "founder"):
                return Response(
                    {"detail": "프로필을 결정할 수 없습니다. proposer_profile 또는 founder_profile 중 하나를 포함하세요."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        profile = "proposer" if has_proposer else ("founder" if has_founder else data.get("profile"))
        Serializer = UserProposerSignupSerializer if profile == "proposer" else UserFounderSignupSerializer

        # 시리얼라이저로 실제 생성까지 맡긴다 (create 사용)
        try:
            serializer = Serializer(data=data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            user = serializer.save()  # ← User와 해당 프로필까지 생성됨
        except IntegrityError:
            return Response({"detail": "이미 존재하는 이메일입니다."}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            det = getattr(e, "detail", None)
            # 이메일 중복을 409로 통일
            if isinstance(det, dict) and "email" in det and any("이미 존재하는 이메일" in str(msg) for msg in det["email"]):
                return Response({"detail": "이미 존재하는 이메일입니다."}, status=status.HTTP_409_CONFLICT)
            raise

        # ----- 여기서부터 자동 로그인(JWT 발급) -----
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        access_exp = datetime.fromtimestamp(access["exp"], tz=dt_timezone.utc).isoformat().replace("+00:00", "Z")
        refresh_exp = datetime.fromtimestamp(refresh["exp"], tz=dt_timezone.utc).isoformat().replace("+00:00", "Z")

        profiles = []
        if hasattr(user, "proposer"):
            profiles.append("proposer")
        if hasattr(user, "founder"):
            profiles.append("founder")

        body = {
            "grant_type": "Bearer",
            "access": {
                "token": str(access),
                "expire_at": access_exp,
            },
            "refresh": {
                "token": str(refresh),
                "expire_at": refresh_exp,
            },
            "profile": profiles,
        }
        return Response(body, status=status.HTTP_201_CREATED)

class AccountsProfileRoot(APIView):
    """
    /accounts/{profile}
      - GET  : 현재 로그인한 사용자의 기본 정보 + 해당 프로필 정보 조회
               (field 쿼리로 부분 조회)
      - POST : 현재 로그인한 사용자에 다른 프로필 생성
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    # ----- GET: 프로필 조회 -----
    def get(self, request, profile: str):
        profile = (profile or "").lower()
        if profile not in ("proposer", "founder"):
            return Response(
                {"detail": "유효하지 않은 profile 입니다. ['proposer', 'founder'] 중 하나를 사용하세요."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        fields = set(request.query_params.getlist("field"))
        fields_given = len(fields) > 0

        base_payload = _user_base_payload(request, user)
        base_allow = {"email", "name", "birth", "sex", "profile_image", "is_marketing_allowed"}
        result = {}

        if fields_given:
            for k in base_allow & fields:
                result[k] = base_payload[k]
        else:
            result.update(base_payload)

        if profile == "proposer":
            if not hasattr(user, "proposer"):
                return Response({"detail": "요청한 프로필이 존재하지 않습니다. 먼저 생성하세요."}, status=status.HTTP_404_NOT_FOUND)

            p = user.proposer
            prof_allow = {"industry", "address", "level"}
            need_profile = (not fields_given) or len(fields & prof_allow) > 0

            if need_profile:
                prof = {}

                if (not fields_given) or ("industry" in fields):
                    prof["industry"] = _labels_from_choices(IndustryChoices, p.industry)

                q = p.proposer_level.all().order_by("-level", "id")
                level_items = []
                for row in q:
                    item = {}
                    if (not fields_given) or ("address" in fields):
                        item["address"] = [row.address]
                    if (not fields_given) or ("level" in fields):
                        item["level"] = row.level
                    if item:
                        level_items.append(item)

                if (not fields_given) or ({"address", "level"} & fields):
                    prof["proposer_level"] = level_items

                if prof:
                    result["proposer_profile"] = prof

        else:
            if not hasattr(user, "founder"):
                return Response({"detail": "요청한 프로필이 존재하지 않습니다. 먼저 생성하세요."}, status=status.HTTP_404_NOT_FOUND)

            f = user.founder
            prof_allow = {"industry", "address", "target", "business_hours"}
            need_profile = (not fields_given) or len(fields & prof_allow) > 0

            if need_profile:
                prof = {}
                if (not fields_given) or ("industry" in fields):
                    prof["industry"] = _labels_from_choices(IndustryChoices, f.industry)
                if (not fields_given) or ("address" in fields):
                    prof["address"] = list(f.address or [])
                if (not fields_given) or ("target" in fields):
                    prof["target"] = _labels_from_choices(FounderTargetChoices, f.target)
                if (not fields_given) or ("business_hours" in fields):
                    prof["business_hours"] = f.business_hours or {}
                if prof:
                    result["founder_profile"] = prof

        # field 값 검증 에러 처리 (옵션: 필요 시 강화)
        invalid = set(fields) - (base_allow | {"industry", "address", "level", "target", "business_hours"})
        if invalid:
            return Response(
                {"detail": "유효하지 않은 field 값입니다.", "invalid_fields": sorted(list(invalid))},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 프로필 전용 필드 검증
        if "level" in fields and profile != "proposer":
            return Response(
                {"detail": f"{profile} 프로필에서 사용할 수 없는 field 입니다.", "invalid_fields": ["level"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ({"target", "business_hours"} & fields) and profile != "founder":
            bad = sorted(list({"target", "business_hours"} & fields))
            return Response(
                {"detail": f"{profile} 프로필에서 사용할 수 없는 field 입니다.", "invalid_fields": bad},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result, status=status.HTTP_200_OK)

    # ----- POST: 프로필 생성 -----
    @transaction.atomic
    def post(self, request, profile: str):
        profile = (profile or "").lower()
        if profile not in ("proposer", "founder"):
            return Response(
                {"detail": "유효하지 않은 profile 입니다. ['proposer', 'founder'] 중 하나를 사용하세요."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        if profile == "proposer" and hasattr(user, "proposer"):
            return Response({"detail": "이미 proposer 프로필이 존재합니다."}, status=status.HTTP_409_CONFLICT)
        if profile == "founder" and hasattr(user, "founder"):
            return Response({"detail": "이미 founder 프로필이 존재합니다."}, status=status.HTTP_409_CONFLICT)

        if profile == "proposer":
            # 시리얼라이저로 생성 (user는 context로 주입)
            serializer = ProposerSerializer(
                data=request.data,
                context={"request": request, "user": user},
            )
            serializer.is_valid(raise_exception=True)
            proposer = serializer.save()

            addr_list = serializer.validated_data.get("address") or []
            industry_labels = ", ".join(_labels_from_choices(IndustryChoices, proposer.industry))
            return Response(
                {"proposer_profile": {"industry": industry_labels, "address": addr_list}},
                status=status.HTTP_200_OK,
            )

        serializer = FounderSerializer(
            data=request.data,
            context={"request": request, "user": user},
        )
        serializer.is_valid(raise_exception=True)
        founder = serializer.save()

        addresses = founder.address or []
        industry_labels = ", ".join(_labels_from_choices(IndustryChoices, founder.industry))
        target_labels = _labels_from_choices(FounderTargetChoices, founder.target)

        return Response(
            {
                "founder_profile": {
                    "industry": industry_labels,
                    "address": addresses,
                    "target": target_labels,
                    "business_hours": founder.business_hours or {},
                }
            },
            status=status.HTTP_200_OK,
        )

class AccountsLocationHistoryRoot(APIView):
    """
    POST /accounts/location-history
    - 좌표 → 법정동 변환 후 LocationHistory에 저장
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1) 요청 검증
        ser = LocationHistoryCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        # 2) proposer 프로필 필수
        proposer = getattr(request.user, "proposer", None)
        if proposer is None:
            return Response(
                {"detail": "proposer 프로필이 존재하지 않습니다. 먼저 생성하세요."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 3) 좌표 → 법정동 주소 변환
        svc = ReverseGeocodingService()
        legal = svc.get_position_to_legal(
            {"latitude": v["latitude"], "longitude": v["longitude"]}
        )
        # legal 예: {"sido": ..., "sigungu": ..., "eupmyundong": ...}

        # 4) 클라이언트 timestamp(ms) → created_at 설정
        created_at = datetime.fromtimestamp(v["timestamp"] / 1000.0, tz=dt_timezone.utc)

        # 5) 저장 (user, created_at 유니크 → 중복시 409)
        try:
            LocationHistory.objects.create(
                user=proposer,
                address=legal,
                created_at=created_at,
            )
        except IntegrityError:
            return Response(
                {"detail": "이미 존재하는 값입니다."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({"detail": "위치기록을 추가했어요."}, status=status.HTTP_201_CREATED)