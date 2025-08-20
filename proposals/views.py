from django.http import HttpRequest
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class ProposerLike(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request:HttpRequest, format=None):
        pass

class ProfileScrap(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request:HttpRequest, profile, format=None):
        pass

    def get(self, request:HttpRequest, profile, format=None):
        address = request.query_params.get('address')
