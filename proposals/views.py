from typing import Literal
from django.http import HttpRequest
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from utils.decorators import validate_path_choices
from .serializers import ProposalIdSerializer
from .services import ProposerLikeProposalService, ProposerScrapProposalService, FounderScrapProposalService

class ProposerLike(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request:HttpRequest, format=None):
        serializer = ProposalIdSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        proposal_id = serializer.validated_data['proposal_id']

        service = ProposerLikeProposalService(request)
        is_created = service.post(proposal_id)

        if is_created:
            return Response(
                { 'detail': '이 제안을 좋아해요.' },
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
        serializer = ProposalIdSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        proposal_id = serializer.validated_data['proposal_id']

        if profile == 'proposer':
            service = ProposerScrapProposalService(request)
        elif profile == 'founder':
            service = FounderScrapProposalService(request)
        is_created = service.post(proposal_id)

        if is_created:
            return Response(
                { 'detail': '이 제안을 스크랩했어요.' },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                { 'detail': '스크랩을 취소했어요.' },
                status=status.HTTP_200_OK,
            )

    def get(self, request:HttpRequest, profile:Literal['proposer','founder'], format=None):
        sido = request.query_params.get('sido')
        sigungu = request.query_params.get('sigungu')
        eupmyundong = request.query_params.get('eupmyundong')

        if profile == 'proposer':
            service = ProposerScrapProposalService(request)
        elif profile == 'founder':
            service = FounderScrapProposalService(request)
        data = service.get(sido, sigungu, eupmyundong)

        return Response(
            data,
            status=status.HTTP_200_OK,
        )
