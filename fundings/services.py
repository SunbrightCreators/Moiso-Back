from django.http import HttpRequest
from utils.decorators import validate_data, validate_permission, validate_unique
from .models import Funding, ProposerLikeFunding, ProposerScrapFunding, FounderScrapFunding
from .serializers import FundingListSerializer

class ProposerLikeFundingService:
    def __init__(self, request:HttpRequest):
        self.request = request

    def post(self, funding_id:int) -> bool:
        '''
        Args:
            funding_id (int): 펀딩 id
        Returns:
            is_created (bool):
                - `True`: 좋아요 추가
                - `False`: 좋아요 삭제
        '''
        obj, created = ProposerLikeFunding.objects.get_or_create(
            user__user=self.request.user,
            funding=funding_id,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

class ProposerScrapFundingService:
    def __init__(self, request:HttpRequest):
        self.request = request

    def post(self, funding_id:int) -> bool:
        '''
        Args:
            funding_id (int): 펀딩 id
        Returns:
            is_created (bool):
                - `True`: 스크랩 추가
                - `False`: 스크랩 삭제
        '''
        obj, created = ProposerScrapFunding.objects.get_or_create(
            user__user=self.request.user,
            funding=funding_id,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

    def get(self, sido:str|None=None, sigungu:str|None=None, eupmyundong:str|None=None):
        fundings = Funding.objects.filter(
            proposer_scrap_funding__user__user=self.request.user,
        ).filter_address(
            sido=sido,
            sigungu=sigungu,
            eupmyundong=eupmyundong,
        ).with_analytics(
        ).with_proposal(
        )
        serializer = FundingListSerializer(fundings, many=True)
        return serializer.data

class FounderScrapFundingService:
    def __init__(self, request:HttpRequest):
        self.request = request

    def post(self, funding_id:int) -> bool:
        '''
        Args:
            funding_id (int): 펀딩 id
        Returns:
            is_created (bool):
                - `True`: 스크랩 추가
                - `False`: 스크랩 삭제
        '''
        obj, created = FounderScrapFunding.objects.get_or_create(
            user__user=self.request.user,
            funding=funding_id,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

    def get(self, sido:str|None=None, sigungu:str|None=None, eupmyundong:str|None=None):
        fundings = Funding.objects.filter(
            founder_scrap_funding__user__user=self.request.user,
        ).filter_address(
            sido=sido,
            sigungu=sigungu,
            eupmyundong=eupmyundong,
        ).with_analytics(
        ).with_proposal(
        )
        serializer = FundingListSerializer(fundings, many=True)
        return serializer.data
