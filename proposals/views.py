from django.http import HttpRequest
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import ProposalIdSerializer
from .services import ProposerLikeProposalService

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
                { 'detail': '이 제안글을 좋아해요.' },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                { 'detail': '좋아요를 취소했어요.' },
                status=status.HTTP_200_OK,
            )

class ProfileScrap(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request:HttpRequest, profile, format=None):
        pass

    def get(self, request:HttpRequest, profile, format=None):
        address = request.query_params.get('address')
