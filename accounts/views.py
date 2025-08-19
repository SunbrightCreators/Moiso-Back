from django.http import HttpRequest
from django.utils.decorators import method_decorator
from utils.decorators import require_query_params
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .serializers import LoginSerializer
from .models import Proposer, Founder

from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer as SJWTokenRefreshSerializer

from .serializers import AccessTokenRefreshSerializer

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
        access_exp = timezone.datetime.fromtimestamp(access["exp"], tz=timezone.utc)
        refresh_exp = timezone.datetime.fromtimestamp(refresh["exp"], tz=timezone.utc)

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
        access_exp = timezone.datetime.fromtimestamp(
            AccessToken(access_str)["exp"], tz=timezone.utc
        ).isoformat().replace("+00:00", "Z")

        refresh_exp = timezone.datetime.fromtimestamp(
            RefreshToken(new_refresh_str)["exp"], tz=timezone.utc
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

