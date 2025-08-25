from django.http import HttpRequest
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .services import RecommendationScrapService

class ProposalCalc(APIView):
    def get(self, request:HttpRequest, format=None):
        return Response(
            '',
            status=status.HTTP_200_OK,
        )

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
