import math
from datetime import datetime
from django.utils import timezone
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

class FundingListSerializer(serializers.ModelSerializer):
    industry = serializers.SerializerMethodField()
    expected_opening_date = serializers.SerializerMethodField()
    address = serializers.JSONField(source='proposal.address')
    radius = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    founder = serializers.SerializerMethodField()
    schedule = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField()
    scraps_count = serializers.IntegerField()

    class Meta:
        model = Funding
        fields = ('id','industry','title','summary','expected_opening_date','address','radius','progress','days_left','image','founder','schedule','likes_count','scraps_count',)

    def get_industry(self, obj):
        proposal = obj.proposal
        return proposal.get_industry_display()

    def get_expected_opening_date(self, obj):
        dates = obj.expected_opening_date.split('-')
        return f'{dates[0]}년 {dates[1]}월'

    def get_radius(self, obj):
        return obj.get_radius_display()

    def get_progress(self, obj):
        goal_amount = obj.goal_amount
        amount = obj.amount or 0
        rate = math.trunc((amount / goal_amount) * 100)
        return {
            'rate': rate,
            'amount': amount,
        }

    def get_days_left(self, obj):
        end_date = datetime.strptime(obj.schedule['end'], '%Y-%m-%d').date()
        today = timezone.localdate()
        diff = end_date - today
        return diff.days

    def get_image(self, obj):
        images = filter(None, [obj.image1, obj.image2, obj.image3])
        return [image.url for image in images]

    def get_founder(self, obj):
        return {
            'name': obj.founder_name,
            'image': obj.founder_image.url if obj.founder_image else None,
        }

    def get_schedule(self, obj):
        end_date = datetime.strptime(obj.schedule['end'], '%Y-%m-%d')
        return {
            'end': end_date.strftime('%Y년 %m월 %d일')
        }
