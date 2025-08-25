from typing import List, Dict, Optional
from django.http import HttpRequest
from rest_framework.exceptions import PermissionDenied
from utils.choices import ProfileChoices, IndustryChoices
from utils.decorators import require_profile
from django.db.models import Count
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
        ).order_by(
            '-proposer_scrap_proposal__created_at',
        )
        serializer = ProposalListSerializer(proposals, many=True)
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
        ).order_by(
            '-founder_scrap_proposal__created_at',
        )
        serializer = ProposalListSerializer(proposals, many=True)
        return serializer.data
    

class ProposalMapService:
    """지도 조회용 DB 쿼리 (응답/지오코딩/is_address 가공은 View에서)"""
    def __init__(self, request: HttpRequest, profile: str):
        self.request = request
        self.profile = (profile or "").lower()

    def _group_counts(self, base_qs, group: str, industry: Optional[str]) -> List[Dict]:
        # 펀딩 없는 것만
        base = base_qs.filter(funding__isnull=True)

        # industry 유효성 + 필터 (None이면 통과)
        if industry:
            valid = {c for c, _ in IndustryChoices.choices}
            if industry not in valid:
                base = base.none()
            else:
                base = base.filter(industry=industry)

        base = base.exclude(**{f"{group}__isnull": True}).exclude(**{group: ""})

        rows = (
            base.values(group)
                .annotate(number=Count("id"))
                .order_by(group)
        )
        return [{"address": r[group], "number": r["number"]} for r in rows]

    def cluster_counts_sido(self, industry: Optional[str]) -> List[Dict]:
        """도(시도) 레벨 클러스터"""
        group = "address__sido"
        base = Proposal.objects.all()
        return self._group_counts(base, group, industry)

    def cluster_counts_sigungu(self, sido: str, industry: Optional[str]) -> List[Dict]:
        """구(시군구) 레벨 클러스터"""
        group = "address__sigungu"
        base = Proposal.objects.filter(address__sido=sido)
        return self._group_counts(base, group, industry)

    def cluster_counts_eupmyundong(self, sido: str, sigungu: str, industry: Optional[str]) -> List[Dict]:
        """동(읍면동) 레벨 클러스터"""
        group = "address__eupmyundong"
        base = Proposal.objects.filter(address__sido=sido, address__sigungu=sigungu)
        return self._group_counts(base, group, industry)
    