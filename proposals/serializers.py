from rest_framework import serializers
from utils.serializer_fields import HumanizedDateTimeField
from .models import Proposal, ProposerScrapProposal, FounderScrapProposal

class ProposalIdSerializer(serializers.Serializer):
    proposal_id = serializers.IntegerField(
        write_only=True,
        required=True,
        allow_null=False,
        min_value=1,
    )

    def validate_proposal_id(self, value):
        if not Proposal.objects.filter(id=value).exists():
            raise serializers.ValidationError('존재하지 않는 제안이에요.')
        return value

class ProposalListSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    created_at = HumanizedDateTimeField()
    user = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField()
    scraps_count = serializers.IntegerField()

    class Meta:
        model = Proposal
        fields = '__all__'
        read_only_fields = '__all__'

    def get_image(self, obj):
        return [obj.image1.url, obj.image2.url, obj.image3.url]

    def get_user(self, obj):
        user = obj.user.user
        return {
            'name': user.name,
            'profile_image': user.profile_image.url or None,
        }

class ProposerScrapProposalSerializer(serializers.ModelSerializer):
    scrapped_at = serializers.DateTimeField(source='created_at')

    class Meta:
        model = ProposerScrapProposal
        fields = ('scrapped_at')

    def to_representation(self, instance):
        proposal_data = ProposalListSerializer(
            instance.proposal,
            context=self.context,
        ).data

        proposal_data['scrapped_at'] = instance.created_at

        return proposal_data

class FounderScrapProposalSerializer(serializers.ModelSerializer):
    scrapped_at = serializers.DateTimeField(source='created_at')

    class Meta:
        model = FounderScrapProposal
        fields = ('scrapped_at')

    def to_representation(self, instance):
        proposal_data = ProposalListSerializer(
            instance.proposal,
            context=self.context,
        ).data

        proposal_data['scrapped_at'] = instance.created_at

        return proposal_data
