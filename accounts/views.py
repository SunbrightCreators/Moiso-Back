from datetime import datetime, timezone as dt_timezone

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction, IntegrityError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenRefreshSerializer as SJWTokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from django.db.utils import ProgrammingError, OperationalError
from django.utils.crypto import get_random_string

from .models import (
    User,
    Proposer,
    ProposerLevel,
    LocationHistory,
    Founder,
)
from .serializers import (
    UserLoginSerializer,
    JwtRefreshRequestSerializer,
    ProposerProfileSerializer,
    FounderProfileSerializer,
    UserProposerSignupSerializer,
    UserFounderSignupSerializer,
)
from utils.choices import IndustryChoices, FounderTargetChoices, SexChoices


# ── Helpers ────────────────────────────────────────────────────────────────
def _labels_from_choices(choices_cls, codes):
    mapping = dict(choices_cls.choices)  # {value: label}
    if isinstance(codes, (list, tuple)):
        return [mapping.get(code, str(code)) for code in codes]
    return mapping.get(codes, str(codes))


def _user_base_payload(user):
    """기본 사용자 정보 JSON (라벨 변환)"""
    return {
        "email": user.email,
        "name": user.name,
        "birth": user.birth,
        "sex": _labels_from_choices(SexChoices, user.sex),
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
                "expired_at": access_exp,
            },
            "refresh": {
                "token": new_refresh_str,
                "expired_at": refresh_exp,
            },
        }
        return Response(body, status=status.HTTP_200_OK)


class AccountsRoot(APIView):
    """
    /accounts/
      - POST   : 회원가입 (Body로 프로필 자동판별: proposer_profile 또는 founder_profile)
      - DELETE : 로그인한 사용자 계정 삭제
    """
    authentication_classes = []  # 기본 비인증 허용
    permission_classes = [AllowAny]

    def get_authenticators(self):
        if self.request and self.request.method == "DELETE":
            return [JWTAuthentication()]
        return super().get_authenticators()

    def get_permissions(self):
        if self.request and self.request.method == "DELETE":
            return [IsAuthenticated()]
        return [AllowAny()]

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

        try:
            serializer = Serializer(data=data)
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            det = getattr(e, "detail", None)
            if isinstance(det, dict) and "email" in det and any("이미 존재하는 이메일" in str(msg) for msg in det["email"]):
                return Response({"detail": "이미 존재하는 이메일입니다."}, status=status.HTTP_409_CONFLICT)
            raise

        v = serializer.validated_data

        try:
            user = User.objects.create_user(
                email=v["email"],
                password=v["password"],
                name=v["name"],
                birth=v["birth"],
                sex=v["sex"],
                is_marketing_allowed=v.get("is_marketing_allowed", False),
            )

            if profile == "proposer":
                p = v["proposer_profile"]
                proposer = Proposer.objects.create(user=user, industry=p["industry"])
                addr_list = p.get("address") or []
                if addr_list:
                    addr0 = addr_list[0]
                    ProposerLevel.objects.create(user=proposer, level=1, address=addr0)
                    LocationHistory.objects.create(user=proposer, address=addr0)
            else:
                f = v["founder_profile"]
                addresses = (f.get("address") or [])[:2]  # 모델 size=2 제한
                Founder.objects.create(
                    user=user,
                    industry=f["industry"],
                    address=addresses,
                    target=f["target"],
                    business_hours=f["business_hours"],
                )

        except IntegrityError:
            return Response({"detail": "이미 존재하는 이메일입니다."}, status=status.HTTP_409_CONFLICT)

        return Response({"detail": "회원가입을 완료했어요."}, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def delete(self, request):
        try:
            user = User.objects.select_for_update().get(pk=request.user.pk)
        except User.DoesNotExist:
            return Response(
                {"detail": "이미 탈퇴한 계정이거나 존재하지 않습니다."},
                status=status.HTTP_410_GONE,
            )

        # 관리자 보호
        if user.is_staff or user.is_superuser:
            return Response(
                {"detail": "관리자 계정은 API로 탈퇴할 수 없습니다."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 1) 하드 삭제 시도 (세이브포인트로 격리)
        try:
            with transaction.atomic():  # <- 내부 세이브포인트
                user.delete()
            return Response({"detail": "계정을 탈퇴했어요."}, status=status.HTTP_200_OK)

        # 2) 연관 테이블 부재 등으로 실패 시 → 소프트 삭제로 폴백
        except (ProgrammingError, OperationalError):
            pass  # 내부 atomic이 롤백하고 나옴, 바깥 트랜잭션은 정상 상태

        # 소프트 삭제(익명화 + 비활성화). email은 UNIQUE이므로 랜덤값으로 치환
        user.email = f"deleted_{user.pk}_{get_random_string(8)}@invalid.local"
        user.name = "탈퇴회원"
        user.is_active = False
        user.is_marketing_allowed = False
        # (프로필 이미지 파일을 실제 운영에서 지울 거면 try/except로 삭제 가능)
        user.save(update_fields=["email", "name", "is_active", "is_marketing_allowed"])

        return Response({"detail": "계정을 탈퇴했어요."}, status=status.HTTP_200_OK)

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

        base_payload = _user_base_payload(user)
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
            serializer = ProposerProfileSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            v = serializer.validated_data

            proposer = Proposer.objects.create(user=user, industry=v["industry"])
            addr_list = v.get("address") or []
            if addr_list:
                first_addr = addr_list[0]
                ProposerLevel.objects.create(user=proposer, level=1, address=first_addr)
                LocationHistory.objects.create(user=proposer, address=first_addr)

            industry_labels = ", ".join(_labels_from_choices(IndustryChoices, v["industry"]))
            return Response(
                {"proposer_profile": {"industry": industry_labels, "address": addr_list}},
                status=status.HTTP_200_OK,
            )

        serializer = FounderProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data

        addresses = (v.get("address") or [])[:2]
        Founder.objects.create(
            user=user,
            industry=v["industry"],
            address=addresses,
            target=v["target"],
            business_hours=v["business_hours"],
        )

        industry_labels = ", ".join(_labels_from_choices(IndustryChoices, v["industry"]))
        target_labels = _labels_from_choices(FounderTargetChoices, v["target"])

        return Response(
            {
                "founder_profile": {
                    "industry": industry_labels,
                    "address": addresses,
                    "target": target_labels,
                    "business_hours": v["business_hours"],
                }
            },
            status=status.HTTP_200_OK,
        )
