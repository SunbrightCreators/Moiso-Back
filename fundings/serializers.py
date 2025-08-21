from rest_framework import serializers
from .models import Funding

class FundingIdSerializer(serializers.Serializer):
    funding_id = serializers.IntegerField(
        write_only=True,
        required=True,
        allow_null=False,
        min_value=1,
    )

    def validate_funding_id(self, value):
        if not Funding.objects.filter(id=value).exists():
            raise serializers.ValidationError('존재하지 않는 펀딩이에요.')
        return value
