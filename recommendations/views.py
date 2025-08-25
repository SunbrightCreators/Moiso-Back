from django.http import HttpRequest
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .services import RecommendationScrapService
from django.http import HttpRequest
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from .services import RecommendationCalcService
from rest_framework.exceptions import PermissionDenied

class ProposalScrapSimilarity(APIView):
    def get(self, request:HttpRequest, format=None):
        service = RecommendationScrapService(request)
        data = service.recommend_founder_scrap_proposal()

        return Response(
            data,
            status=status.HTTP_200_OK,
        )

class ProposalFundingSuccessSimilarity(APIView):
    def get(self, request:HttpRequest, format=None):
        return Response(
            '',
            status=status.HTTP_200_OK,
        )

class ProposalCalc(APIView):
    """
    GET /recommendations/proposal/calc
      - Founder 전용: 단순 계산식 추천
      - Founder.address(≤2) 전체를 후보로 사용 (쿼리로 동을 고르지 않음)
      - limit (선택): 기본 10, 최대 50
      - 응답: ProposalListSerializer 목록 (점수 노출 없음)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: HttpRequest, format=None):
        limit = request.query_params.get("limit")
        svc = RecommendationCalcService(request)
        try:
            data = svc.recommend_calc(limit=limit)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        return Response(data, status=status.HTTP_200_OK)

