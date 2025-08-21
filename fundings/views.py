from typing import Literal
from django.http import HttpRequest
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from utils.decorators import validate_path_choices
from .serializers import FundingIdSerializer
from .services import ProposerLikeFundingService, ProposerScrapFundingService, FounderScrapFundingService

class ProposerLike(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request:HttpRequest, format=None):
        serializer = FundingIdSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        funding_id = serializer.validated_data['funding_id']

        service = ProposerLikeFundingService(request)
        is_created = service.post(funding_id)

        if is_created:
            return Response(
                { 'detail': '이 펀딩을 좋아해요.' },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                { 'detail': '좋아요를 취소했어요.' },
                status=status.HTTP_200_OK,
            )

@method_decorator(validate_path_choices(profile=('proposer', 'founder')), name='dispatch')
class ProfileScrap(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request:HttpRequest, profile:Literal['proposer','founder'], format=None):
        serializer = FundingIdSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        funding_id = serializer.validated_data['funding_id']

        if profile == 'proposer':
            service = ProposerScrapFundingService(request)
        elif profile == 'founder':
            service = FounderScrapFundingService(request)
        is_created = service.post(funding_id)

        if is_created:
            return Response(
                { 'detail': '이 펀딩을 스크랩했어요.' },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                { 'detail': '스크랩을 취소했어요.' },
                status=status.HTTP_200_OK,
            )
