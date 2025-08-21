from django.http import HttpRequest
from utils.decorators import validate_data, validate_permission, validate_unique
from .models import ProposerLikeProposal, ProposerScrapProposal, FounderScrapProposal
from .serializers import ProposerScrapProposalSerializer, FounderScrapProposalSerializer

class ProposerLikeProposalService:
    def __init__(self, request:HttpRequest):
        self.request = request

    def post(self, proposal_id:int) -> bool:
        '''
        Args:
            proposal_id (int): 제안 id
        Returns:
            is_created (bool):
                - `True`: 좋아요 추가
                - `False`: 좋아요 삭제
        '''
        obj, created = ProposerLikeProposal.objects.get_or_create(
            user__user=self.request.user,
            proposal=proposal_id,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

class ProposerScrapProposalService:
    def __init__(self, request:HttpRequest):
        self.request = request

    def post(self, proposal_id:int) -> bool:
        '''
        Args:
            proposal_id (int): 제안 id
        Returns:
            is_created (bool):
                - `True`: 스크랩 추가
                - `False`: 스크랩 삭제
        '''
        obj, created = ProposerScrapProposal.objects.get_or_create(
            user__user=self.request.user,
            proposal=proposal_id,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

    def get(self, sido:str|None=None, sigungu:str|None=None, eupmyundong:str|None=None):
        proposer_scrap_proposals = ProposerScrapProposal.objects.filter(
            user__user=self.request.user,
            proposal__address__sido=sido,
            proposal__address__sigungu=sigungu,
            proposal__address__eupmyundong=eupmyundong,
        ).select_related(
            'proposal__user__user',
        )
        serializer = ProposerScrapProposalSerializer(proposer_scrap_proposals)
        return serializer.data

class FounderScrapProposalService:
    def __init__(self, request:HttpRequest):
        self.request = request

    def post(self, proposal_id:int) -> bool:
        '''
        Args:
            proposal_id (int): 제안 id
        Returns:
            is_created (bool):
                - `True`: 스크랩 추가
                - `False`: 스크랩 삭제
        '''
        obj, created = FounderScrapProposal.objects.get_or_create(
            user__user=self.request.user,
            proposal=proposal_id,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

    def get(self, sido:str|None=None, sigungu:str|None=None, eupmyundong:str|None=None):
        founder_scrap_proposals = FounderScrapProposal.objects.filter(
            user__user=self.request.user,
            proposal__address__sido=sido,
            proposal__address__sigungu=sigungu,
            proposal__address__eupmyundong=eupmyundong,
        ).select_related(
            'proposal__user__user',
        )
        serializer = FounderScrapProposalSerializer(founder_scrap_proposals)
        return serializer.data
