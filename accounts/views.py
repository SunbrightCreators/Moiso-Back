from django.http import HttpRequest
from django.utils.decorators import method_decorator
from utils.decorators import require_query_params
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from .serializers import LoginSerializer
from .models import Proposer, Founder

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


