from django.http import HttpRequest
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

class ProposalOverall(APIView):
    def get(self, request:HttpRequest, format=None):
        return Response(
            '',
            status=status.HTTP_200_OK,
        )

class ProposalScrapSimilarity(APIView):
    def get(self, request:HttpRequest, format=None):
        return Response(
            '',
            status=status.HTTP_200_OK,
        )

class ProposalFundingSuccessSimilarity(APIView):
    def get(self, request:HttpRequest, format=None):
        return Response(
            '',
            status=status.HTTP_200_OK,
        )
