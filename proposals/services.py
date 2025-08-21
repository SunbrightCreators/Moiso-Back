from django.http import HttpRequest
from utils.decorators import validate_data, validate_permission, validate_unique
from .models import ProposerLikeProposal, ProposerScrapProposal, FounderScrapProposal

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
