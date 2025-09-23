from django.http import HttpRequest
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .services import RecommendationScrapService, RecommendationCalcService
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import PermissionDenied

class ProposalCalc(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            svc = RecommendationCalcService(request)
            data = svc.recommend_calc()
            return Response(data if data else [], status=status.HTTP_200_OK)
        except PermissionDenied as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

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
