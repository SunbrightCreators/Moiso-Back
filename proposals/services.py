from django.http import HttpRequest
from rest_framework.exceptions import PermissionDenied
from utils.choices import ProfileChoices
from utils.decorators import require_profile
from .models import Proposal, ProposerLikeProposal, ProposerScrapProposal, FounderScrapProposal
from .serializers import ProposalListSerializer

class ProposerLikeProposalService:
    def __init__(self, request:HttpRequest):
        self.request = request

    @require_profile(ProfileChoices.proposer)
    def post(self, proposal_id:int) -> bool:
        '''
        Args:
            proposal_id (int): 제안 id
        Returns:
            is_created (bool):
                - `True`: 좋아요 추가
                - `False`: 좋아요 삭제
        '''
        proposal = Proposal.objects.get(id=proposal_id)
        if proposal.user.user == self.request.user:
            raise PermissionDenied('자신의 제안을 좋아할 수 없어요.')

        obj, created = ProposerLikeProposal.objects.get_or_create(
            user=self.request.user.proposer,
            proposal=proposal,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

class ProposerScrapProposalService:
    def __init__(self, request:HttpRequest):
        self.request = request

    @require_profile(ProfileChoices.proposer)
    def post(self, proposal_id:int) -> bool:
        '''
        Args:
            proposal_id (int): 제안 id
        Returns:
            is_created (bool):
                - `True`: 스크랩 추가
                - `False`: 스크랩 삭제
        '''
        proposal = Proposal.objects.get(id=proposal_id)
        if proposal.user.user == self.request.user:
            raise PermissionDenied('자신의 제안을 스크랩할 수 없어요.')

        obj, created = ProposerScrapProposal.objects.get_or_create(
            user=self.request.user.proposer,
            proposal=proposal,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

    @require_profile(ProfileChoices.proposer)
    def get(self, sido:str|None=None, sigungu:str|None=None, eupmyundong:str|None=None):
        proposals = Proposal.objects.filter(
            proposer_scrap_proposal__user=self.request.user.proposer,
        ).filter_address(
            sido=sido,
            sigungu=sigungu,
            eupmyundong=eupmyundong,
        ).with_analytics(
        ).with_user(
        )
        serializer = ProposalListSerializer(proposals)
        return serializer.data

class FounderScrapProposalService:
    def __init__(self, request:HttpRequest):
        self.request = request

    @require_profile(ProfileChoices.founder)
    def post(self, proposal_id:int) -> bool:
        '''
        Args:
            proposal_id (int): 제안 id
        Returns:
            is_created (bool):
                - `True`: 스크랩 추가
                - `False`: 스크랩 삭제
        '''
        proposal = Proposal.objects.get(id=proposal_id)
        if proposal.user.user == self.request.user:
            raise PermissionDenied('자신의 제안을 스크랩할 수 없어요.')

        obj, created = FounderScrapProposal.objects.get_or_create(
            user=self.request.user.founder,
            proposal=proposal,
        )
        if created:
            return True
        else:
            obj.delete()
            return False

    @require_profile(ProfileChoices.founder)
    def get(self, sido:str|None=None, sigungu:str|None=None, eupmyundong:str|None=None):
        proposals = Proposal.objects.filter(
            founder_scrap_proposal__user=self.request.user.founder,
        ).filter_address(
            sido=sido,
            sigungu=sigungu,
            eupmyundong=eupmyundong,
        ).with_analytics(
        ).with_user(
        )
        serializer = ProposalListSerializer(proposals)
        return serializer.data
