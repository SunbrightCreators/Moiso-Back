import math
from datetime import datetime
from django.utils import timezone
from rest_framework import serializers
from .models import Funding, Reward

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

    is_liked   = serializers.SerializerMethodField()
    is_scrapped = serializers.SerializerMethodField()

    class Meta:
        model = Funding
        fields = (
            'id', 'industry', 'title', 'summary', 'expected_opening_date',
            'address', 'radius', 'progress', 'days_left', 'image', 'founder',
            'schedule', 'likes_count', 'scraps_count', 'is_scrapped','is_liked'
        )

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
    def get_is_liked(self, obj):
        # 1) annotate 우선
        val = getattr(obj, "is_liked", None)
        if val is not None:
            return bool(val)
        # 2) 폴백
        request = self.context.get("request")
        profile = (self.context.get("profile") or "").lower()
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        if profile != "proposer":
            return False
        from .models import ProposerLikeFunding
        return ProposerLikeFunding.objects.filter(
            funding=obj, user=request.user.proposer
        ).exists()

    def get_is_scrapped(self, obj):
        val = getattr(obj, "is_scrapped", None)
        if val is not None:
            return bool(val)
        request = self.context.get("request")
        profile = (self.context.get("profile") or "").lower()
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        if profile == "proposer":
            from .models import ProposerScrapFunding
            return ProposerScrapFunding.objects.filter(
                funding=obj, user=request.user.proposer
            ).exists()
        if profile == "founder":
            from .models import FounderScrapFunding
            return FounderScrapFunding.objects.filter(
                funding=obj, user=request.user.founder
            ).exists()
        return False
    

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


#  지도 상세 리스트용(동 이하): position 추가
class FundingMapSerializer(FundingListSerializer):
    position = serializers.SerializerMethodField()

    class Meta(FundingListSerializer.Meta):
        fields = FundingListSerializer.Meta.fields + ('position',)

    def get_position(self, obj):
        geocoder = self.context.get("geocoder")   # ← 뷰에서 주입
        addr = (obj.proposal.address or {})
        full_addr = " ".join(filter(None, [addr.get("sido"), addr.get("sigungu"), addr.get("eupmyundong")]))
        try:
            pos = geocoder.get_address_to_position(query_address=full_addr)
        except Exception:
            pos = {"latitude": None, "longitude": None}
        return {"latitude": pos.get("latitude"), "longitude": pos.get("longitude")}
    
    # to_representation에서 founder면 is_liked 제거 하는 처리 유지
    def to_representation(self, instance):
        data = super().to_representation(instance)
        profile = (self.context.get("profile") or "").lower()
        if profile == "founder":
            data.pop("is_liked", None) 
        return data


#집계 응답
class RegionClusterSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    address = serializers.CharField()
    position = serializers.DictField()   # {"latitude": float, "longitude": float}
    number = serializers.IntegerField()


class RewardItemSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()

    class Meta:
        model = Reward
        fields = ("id", "category", "title", "amount")

    def get_category(self, obj):
        return obj.get_category_display()


class _ProposalUserMiniSerializer(serializers.Serializer):
    name = serializers.CharField()
    profile_image = serializers.CharField(allow_null=True)


class _ProposalBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    industry = serializers.CharField()
    title = serializers.CharField()
    content = serializers.CharField()
    business_hours = serializers.DictField()
    address = serializers.DictField()
    radius = serializers.CharField()
    image = serializers.ListField(child=serializers.CharField())
    user = _ProposalUserMiniSerializer()
    created_at = serializers.CharField()
    likes_count = serializers.IntegerField()
    scraps_count = serializers.IntegerField()


class FundingDetailBaseSerializer(FundingListSerializer):
    """
    상세는 반드시 FundingListSerializer 상속!
    (요구사항) 지도 조회(=FundingList) + position + 상세 필드 추가
    """
    # 지도에서 필요한 position을 상세에도 노출
    position = serializers.SerializerMethodField()

    goal_amount = serializers.IntegerField()
    video = serializers.SerializerMethodField()
    amount_description = serializers.CharField()
    schedule_description = serializers.CharField()
    content = serializers.CharField()
    business_hours = serializers.JSONField()
    reward = serializers.SerializerMethodField()
    contact = serializers.CharField()
    policy = serializers.CharField()
    expected_problem = serializers.CharField()
    proposal = serializers.SerializerMethodField()

    class Meta(FundingListSerializer.Meta):
        fields = FundingListSerializer.Meta.fields + (
            "position",
            "goal_amount", "video", "amount_description", "schedule_description",
            "content", "business_hours", "reward", "contact", "policy",
            "expected_problem", "proposal",
        )

    # 공통: 상세에서 schedule은 start/end 모두 '.' 포맷
    def get_schedule(self, obj):
        s = datetime.strptime(obj.schedule['start'], '%Y-%m-%d').strftime('%Y.%m.%d.')
        e = datetime.strptime(obj.schedule['end'],   '%Y-%m-%d').strftime('%Y.%m.%d.')
        return {"start": s, "end": e}

    def get_position(self, obj):
        pos = getattr(obj.proposal, "position", None)
        if isinstance(pos, dict):
            lat, lng = pos.get("latitude"), pos.get("longitude")
            if lat is not None and lng is not None:
                return {"latitude": float(lat), "longitude": float(lng)}
        return None

    def get_video(self, obj):
        return obj.video.url if obj.video else None

    def get_reward(self, obj):
        return RewardItemSerializer(obj.reward.all().only("id", "category", "title", "amount"), many=True).data

    def _kr_timesince(self, dt):
        if not dt:
            return ""
        delta = timezone.now() - dt
        sec = int(delta.total_seconds())
        if sec < 60:   return f"{sec}초 전"
        m = sec // 60
        if m < 60:     return f"{m}분 전"
        h = m // 60
        if h < 24:     return f"{h}시간 전"
        d = h // 24
        return f"{d}일 전"

    def _mask_name(self, name: str) -> str:
        if not name: return ""
        return name[0] + ("*" * (len(name) - 1))

    def get_proposal(self, obj: Funding):
        prop = obj.proposal

        # 제안글 이미지(필드명이 image1/2/3이라고 가정)
        images = []
        for key in ("image1", "image2", "image3"):
            im = getattr(prop, key, None)
            if im:
                images.append(im.url)

        user_obj = getattr(prop, "user", None)
        user_name = getattr(user_obj, "name", None) or getattr(user_obj, "nickname", "") or ""
        profile_image = getattr(user_obj, "profile_image", None)
        if hasattr(profile_image, "url"):
            profile_image = profile_image.url

        data = {
            "id": prop.id,
            "industry": prop.get_industry_display(),
            "title": prop.title,
            "content": prop.content,
            "business_hours": prop.business_hours,
            "address": prop.address,
            "radius": getattr(prop, "get_radius_display", lambda: "")(),
            "image": images,
            "user": {"name": self._mask_name(user_name), "profile_image": profile_image},
            "created_at": self._kr_timesince(getattr(prop, "created_at", None)),
            # 제안글 좋아요/스크랩 별도 집계가 없다면 펀딩의 집계값 재사용
            "likes_count": getattr(prop, "likes_count", None) or getattr(obj, "likes_count", 0),
            "scraps_count": getattr(prop, "scraps_count", None) or getattr(obj, "scraps_count", 0),
        }
        # 타입 검증
        return _ProposalBriefSerializer(data).data

    # 상세에서는 founder 블록에 description도 포함
    def get_founder(self, obj):
        base = super().get_founder(obj)
        base["description"] = obj.founder_description
        return base


class FundingDetailProposerSerializer(FundingDetailBaseSerializer):
    """
    profile=proposer
    - progress: 정수 값 유지(부모 그대로)
    - my_payment 포함
    """
    my_payment = serializers.SerializerMethodField()

    class Meta(FundingDetailBaseSerializer.Meta):
        fields = FundingDetailBaseSerializer.Meta.fields + ("my_payment",)

    def get_my_payment(self, obj):
        # services에서 context로 계산 결과를 전달
        return self.context.get("my_payment")


class FundingDetailFounderSerializer(FundingDetailBaseSerializer):
    """
    profile=founder
    - progress: 문자열 포맷 ("64%", "425,789원")
    - likes_analysis 포함 (created_at은 상단에 없음 → Base/Founder 모두 상단에 created_at 추가하지 않음)
    """
    likes_analysis = serializers.SerializerMethodField()

    class Meta(FundingDetailBaseSerializer.Meta):
        fields = FundingDetailBaseSerializer.Meta.fields + ("likes_analysis",)

    def get_progress(self, obj):
        goal = obj.goal_amount or 0
        amount = obj.amount or 0
        rate = math.trunc((amount / goal) * 100) if goal else 0
        return {"rate": f"{rate}%", "amount": f"{amount:,}원"}

    def get_likes_analysis(self, obj):
        return self.context.get("likes_analysis")
    
class FundingMyCreatedItemSerializer(serializers.ModelSerializer):
    schedule = serializers.SerializerMethodField()

    class Meta:
        model = Funding
        fields = ("id", "title", "schedule")

    def get_schedule(self, obj):
        # "2025-08-24" -> "2025.08.24."
        end = obj.schedule.get("end")
        if not end:
            return {"end": None}
        try:
            end_dt = datetime.strptime(end, "%Y-%m-%d")
            return {"end": end_dt.strftime("%Y.%m.%d.")}
        except Exception:
            return {"end": end}  # 실패 시 원문 반환
