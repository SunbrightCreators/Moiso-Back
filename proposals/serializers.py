from rest_framework import serializers
from .models import Proposal

class ProposalIdSerializer(serializers.Serializer):
    proposal_id = serializers.IntegerField(
        write_only=True,
        required=True,
        allow_null=False,
        min_value=1,
        error_messages={
            'required': 'proposal_id는 반드시 입력해야 합니다.',
            'null': 'proposal_id에 null 값을 입력할 수 없습니다.',
            'invalid': 'proposal_id는 정수여야 합니다.',
            'min_value': 'proposal_id는 1 이상이어야 합니다.',
        },
    )

    def validate_proposal_id(self, value):
        if not Proposal.objects.filter(id=value).exists():
            raise serializers.ValidationError('존재하지 않는 제안이에요.')
        return value
