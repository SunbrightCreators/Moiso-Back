from rest_framework import serializers
from utils.serializer_fields import HumanizedDateTimeField
from .models import Proposal

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
    user = serializers.SerializerMethodField()
    created_at = HumanizedDateTimeField()
    likes_count = serializers.IntegerField()
    scraps_count = serializers.IntegerField()

    class Meta:
        model = Proposal
        fields = '__all__'

    def get_image(self, obj):
        images = filter(None, [obj.image1, obj.image2, obj.image3])
        return [image.url for image in images]

    def get_user(self, obj):
        user = obj.user.user
        return {
            'name': user.name,
            'profile_image': user.profile_image.url if user.profile_image else None,
        }
