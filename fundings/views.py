from django.http import HttpRequest
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from utils.decorators import validate_path_choices, method_decorator
from django.views.decorators.cache import never_cache

from utils.choices import ProfileChoices
from utils.decorators import validate_path_choices
from .serializers import FundingIdSerializer
from .services import (
    ProposerLikeFundingService, 
    ProposerScrapFundingService, 
    FounderScrapFundingService, 
    FundingMapService, 
    FundingDetailService,
     FounderMyCreatedFundingService
)

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

@method_decorator(validate_path_choices(profile=ProfileChoices.values), name='dispatch')
class ProfileScrap(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request:HttpRequest, profile, format=None):
        serializer = FundingIdSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        funding_id = serializer.validated_data['funding_id']

        if profile == ProfileChoices.proposer.value:
            service = ProposerScrapFundingService(request)
        elif profile == ProfileChoices.founder.value:
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

    def get(self, request:HttpRequest, profile, format=None):
        sido = request.query_params.get('sido')
        sigungu = request.query_params.get('sigungu')
        eupmyundong = request.query_params.get('eupmyundong')

        if profile == ProfileChoices.proposer.value:
            service = ProposerScrapFundingService(request)
        elif profile == ProfileChoices.founder.value:
            service = FounderScrapFundingService(request)
        data = service.get(sido, sigungu, eupmyundong)

        return Response(
            data,
            status=status.HTTP_200_OK,
        )
    
@method_decorator(never_cache, name='dispatch')
class FundingMapView(APIView):
    """
    GET /fundings/{zoom}?sido=&sigungu=&eupmyundong=&industry=&order=
      - 10000: 도(시·도) 집계
      - 2000 : 구/군 집계
      - 500  : 동 집계
      - 0    : 동 이하 상세 리스트 (진행중만, 쿼리 사용)
    ※ queryset 은 with_analytics().with_proposal() 강제 (서비스 내부에서 보장)
    """

    def get(self, request: HttpRequest, zoom: int, *args, **kwargs):
        svc = FundingMapService(request)
        if zoom == 0:
            data = svc.list_in_dong()
            return Response(data, status=status.HTTP_200_OK)
        try:
            data = svc.cluster(zoom)
        except ValueError:
            return Response({'detail': '허용되지 않은 zoom 값입니다. (0|500|2000|10000)'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(data, status=status.HTTP_200_OK)
    
@method_decorator(validate_path_choices(profile=ProfileChoices.values), name='dispatch')
class FundingDetailView(APIView):
    """
    GET /fundings/{funding_id}/{profile}
    """
    def get(self, request: HttpRequest, funding_id: int, profile: str, *args, **kwargs):
        svc = FundingDetailService(request)
        data = svc.get(funding_id, profile)
        return Response(data, status=status.HTTP_200_OK)
    
class FounderMyCreatedView(APIView):
    """
    GET /fundings/founder/my-created
    현재 로그인한 Founder가 작성한 펀딩을 상태별(진행/성공/실패) 최신순으로 반환
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: HttpRequest, *args, **kwargs):
        svc = FounderMyCreatedFundingService(request)
        data = svc.get()
        return Response(data, status=200)
