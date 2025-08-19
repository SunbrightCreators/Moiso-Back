from django.http import HttpRequest
from django.utils.decorators import method_decorator
from utils.decorators import require_query_params
from django.utils import timezone
from datetime import datetime, timezone as dt_timezone
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .serializers import LoginSerializer
from .models import *
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer as SJWTokenRefreshSerializer
from django.db import transaction, IntegrityError

from .serializers import AccessTokenRefreshSerializer, ProposerSignupSerializer, FounderSignupSerializer

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # JWT 발급
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token  # AccessToken 인스턴스

        # 만료 시각을 토큰의 exp 클레임에서 정확히 계산
        access_exp = datetime.fromtimestamp(access["exp"], tz=dt_timezone.utc)
        refresh_exp = datetime.fromtimestamp(refresh["exp"], tz=dt_timezone.utc)


        # profile 배열 구성
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
    

class AccessTokenIssueView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # 1) 입력 검증 (누락/null/blank 처리)
        serializer = AccessTokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_str = serializer.validated_data["refresh_token"]

        # 2) SimpleJWT의 refresh 로직을 그대로 사용 (회전/검증 포함)
        sjw = SJWTokenRefreshSerializer(data={"refresh": refresh_str})
        sjw.is_valid(raise_exception=True)
        sjw_data = sjw.validated_data  # {'access': '...', ['refresh': '...']}

        access_str = sjw_data["access"]
        # 회전 설정에 따라 새 refresh가 있을 수도/없을 수도 있음
        new_refresh_str = sjw_data.get("refresh", refresh_str)

        # 3) 만료시각 계산 (exp → ISO8601 'Z')
        access_exp = datetime.fromtimestamp(
        AccessToken(access_str)["exp"], tz=dt_timezone.utc
        ).isoformat().replace("+00:00", "Z")

        refresh_exp = datetime.fromtimestamp(
        RefreshToken(new_refresh_str)["exp"], tz=dt_timezone.utc
        ).isoformat().replace("+00:00", "Z")


        # 4) 응답 포맷 (네 명세: expired_at 사용)
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


class SignupView(APIView):
    """
    POST /accounts
    Body 키로 프로필 자동 판별:
      - proposer_profile 있으면 proposer
      - founder_profile  있으면 founder
    둘 다/둘 다 없음 → 400
    """
    permission_classes = [AllowAny]

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
        Serializer = ProposerSignupSerializer if profile == "proposer" else FounderSignupSerializer

        # 입력 검증
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
            # 1) 사용자 생성
            user = User.objects.create_user(
                email=v["email"],
                password=v["password"],
                name=v["name"],
                birth=v["birth"],
                sex=v["sex"],
                is_marketing_allowed=v.get("is_marketing_allowed", False),
            )

            # 2) 프로필 생성
            if profile == "proposer":
                p = v["proposer_profile"]
                proposer = Proposer.objects.create(
                    user=user,
                    industry=p["industry"],
                )
                # 주소가 들어오면 첫 주소를 초기 레벨/히스토리에 기록
                addr_list = p.get("address") or []
                if addr_list:
                    addr0 = addr_list[0]
                    ProposerLevel.objects.create(user=proposer, level=1, address=addr0)
                    LocationHistory.objects.create(user=proposer, address=addr0)

            else:  # founder
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
            # UNIQUE 충돌 등(동시성 포함)
            return Response({"detail": "이미 존재하는 이메일입니다."}, status=status.HTTP_409_CONFLICT)

        return Response({"detail": "회원가입을 완료했어요."}, status=status.HTTP_201_CREATED)
