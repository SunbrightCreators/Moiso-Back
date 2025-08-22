from django.http import HttpRequest
from rest_framework.exceptions import PermissionDenied
from utils.choices import ProfileChoices
from utils.decorators import require_profile
from .models import Funding, ProposerLikeFunding, ProposerScrapFunding, FounderScrapFunding
from .serializers import FundingListSerializer

class ProposerLikeFundingService:
    def __init__(self, request:HttpRequest):
        self.request = request

    @require_profile(ProfileChoices.proposer)
    def post(self, funding_id:int) -> bool:
        '''
        Args:
            funding_id (int): 펀딩 id
        Returns:
            is_created (bool):
                - `True`: 좋아요 추가
                - `False`: 좋아요 삭제
        '''
        funding = Funding.objects.get(id=funding_id)
        if funding.user.user == self.request.user:
            raise PermissionDenied('자신의 펀딩을 좋아할 수 없어요.')

        obj, created = ProposerLikeFunding.objects.get_or_create(
            user=self.request.user.proposer,
            funding=funding,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

class ProposerScrapFundingService:
    def __init__(self, request:HttpRequest):
        self.request = request

    @require_profile(ProfileChoices.proposer)
    def post(self, funding_id:int) -> bool:
        '''
        Args:
            funding_id (int): 펀딩 id
        Returns:
            is_created (bool):
                - `True`: 스크랩 추가
                - `False`: 스크랩 삭제
        '''
        funding = Funding.objects.get(id=funding_id)
        if funding.user.user == self.request.user:
            raise PermissionDenied('자신의 펀딩을 스크랩할 수 없어요.')

        obj, created = ProposerScrapFunding.objects.get_or_create(
            user=self.request.user.proposer,
            funding=funding,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

    @require_profile(ProfileChoices.proposer)
    def get(self, sido:str|None=None, sigungu:str|None=None, eupmyundong:str|None=None):
        fundings = Funding.objects.filter(
            proposer_scrap_funding__user=self.request.user.proposer,
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

    @require_profile(ProfileChoices.founder)
    def post(self, funding_id:int) -> bool:
        '''
        Args:
            funding_id (int): 펀딩 id
        Returns:
            is_created (bool):
                - `True`: 스크랩 추가
                - `False`: 스크랩 삭제
        '''
        funding = Funding.objects.get(id=funding_id)
        if funding.user.user == self.request.user:
            raise PermissionDenied('자신의 펀딩을 스크랩할 수 없어요.')

        obj, created = FounderScrapFunding.objects.get_or_create(
            user=self.request.user.founder,
            funding=funding,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

    @require_profile(ProfileChoices.founder)
    def get(self, sido:str|None=None, sigungu:str|None=None, eupmyundong:str|None=None):
        fundings = Funding.objects.filter(
            founder_scrap_funding__user=self.request.user.founder,
        ).filter_address(
            sido=sido,
            sigungu=sigungu,
            eupmyundong=eupmyundong,
        ).with_analytics(
        ).with_proposal(
        )
        serializer = FundingListSerializer(fundings, many=True)
        return serializer.data
