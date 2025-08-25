import math
from datetime import datetime
from django.utils import timezone
from rest_framework import serializers
from .models import Funding, Reward
from utils.serializer_fields import HumanizedDateTimeField

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

    is_scrapped = serializers.BooleanField(read_only=True, default=False)
    is_liked = serializers.BooleanField(read_only=True, default=False)

    is_address = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Funding
        fields = (
            'id', 'industry', 'title', 'summary', 'expected_opening_date',
            'address', 'radius', 'progress', 'days_left', 'image', 'founder',
            'schedule', 'likes_count', 'scraps_count', 'is_liked','is_scrapped', 'is_address',
        )
    def get_industry(self, obj):
        return obj.proposal.get_industry_display()

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
        try:
            end = obj.schedule.get("end")  # "YYYY-MM-DD"
            end_date = datetime.strptime(end, "%Y-%m-%d").date()
            today = timezone.localdate()
            return (end_date - today).days
        except Exception:
            return None

    def get_image(self, obj):
        images = []
        for k in ("image1", "image2", "image3"):
            f = getattr(obj, k, None)
            if f:
                try:
                    images.append(f.url)
                except Exception:
                    pass
        return images

    def get_founder(self, obj):
        # 상세에서 super().get_founder(obj)로 재사용됨
        img = None
        if getattr(obj, "founder_image", None):
            try:
                img = obj.founder_image.url
            except Exception:
                img = None
        return {"name": obj.founder_name, "image": img}

    def get_schedule(self, obj):
        # 리스트에서는 'end'만 "YYYY년 MM월 DD일" 포맷 (상세는 start/end 모두 '.' 포맷)
        try:
            end = obj.schedule.get("end")
            end_dt = datetime.strptime(end, "%Y-%m-%d")
            return {"end": end_dt.strftime("%Y년 %m월 %d일")}
        except Exception:
            return {"end": obj.schedule.get("end")}

    def validate_funding_id(self, value):
        if not Funding.objects.filter(id=value).exists():
            raise serializers.ValidationError('존재하지 않는 펀딩이에요.')
        return value
    
    def to_representation(self, instance):
        data = super().to_representation(instance)

        profile = (self.context.get("profile") or "").lower()
        if profile == "founder":
            data.pop("is_liked", None)

        # ✅ 폴백: viewer_addr가 없으면 request/profile로 복원
        viewer_addr = self.context.get("viewer_addr")
        if viewer_addr is None:
            try:
                from utils.helpers import resolve_viewer_addr
                req = self.context.get("request")
                usr = getattr(req, "user", None)
                viewer_addr = resolve_viewer_addr(usr, profile)
            except Exception:
                viewer_addr = None

        proposal_addr = data.get("address") or {}
        data["is_address"] = self._compute_is_address(
            viewer_addr=viewer_addr,
            proposal_addr=proposal_addr,
        )
        return data
    
    def _compute_is_address(self, *, viewer_addr, proposal_addr: dict) -> bool:
        """viewer_addr(단일 dict 또는 list)와 proposal_addr가 시/군구/읍면동까지 모두 일치하면 True"""
        if not proposal_addr:
            return False
        sido = proposal_addr.get("sido")
        sigungu = proposal_addr.get("sigungu")
        eup = proposal_addr.get("eupmyundong")

        def _one(a: dict) -> bool:
            if not isinstance(a, dict): 
                return False
            return (
                a.get("sido") == sido and
                a.get("sigungu") == sigungu and
                a.get("eupmyundong") == eup
            )

        v = viewer_addr
        if not v:
            return False
        if isinstance(v, list):
            return any(_one(a) for a in v)
        if isinstance(v, dict):
            return _one(v)
        return False


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


class RewardItemSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()

    class Meta:
        model = Reward
        fields = ("id", "category", "title", "amount")

    def get_category(self, obj):
        return obj.get_category_display()
    

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
    status = serializers.SerializerMethodField()

    class Meta(FundingListSerializer.Meta):
        fields = FundingListSerializer.Meta.fields + (
            "position",
            "goal_amount", "video", "amount_description", "schedule_description",
            "content", "business_hours", "reward", "contact", "policy",
            "expected_problem", "proposal", "status",
        )
    
    # 상세는 제안글의 좌표 사용
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
    
    # 공통: 상세에서 schedule은 start/end 모두 '.' 포맷
    def get_schedule(self, obj):
        s = datetime.strptime(obj.schedule['start'], '%Y-%m-%d').strftime('%Y.%m.%d.')
        e = datetime.strptime(obj.schedule['end'],   '%Y-%m-%d').strftime('%Y.%m.%d.')
        return {"start": s, "end": e}


    def get_proposal(self, obj: Funding):
        prop = obj.proposal

        # 이미지
        images = []
        for key in ("image1", "image2", "image3"):
            im = getattr(prop, key, None)
            if im:
                images.append(im.url)

        # 제안자(user) → accounts.Proposer → accounts.User
        proposer  = getattr(prop, "user", None)
        core_user = getattr(proposer, "user", None)

        raw_name = (getattr(core_user, "name", "") or getattr(core_user, "nickname", "") or "")
        if not raw_name:
            masked_name = ""
        elif len(raw_name) == 1:
            masked_name = raw_name + "*"
        else:
            masked_name = raw_name[0] + "**"

        # 프로필 이미지(문자열/파일 모두 방어) + 절대 URL
        profile_image = None
        pi = getattr(core_user, "profile_image", None)
        rel = None
        if isinstance(pi, str) and pi:
            rel = pi
        elif getattr(pi, "name", None):  # 파일이 실제로 연결되어 있을 때만
            try:
                rel = pi.url
            except Exception:
                rel = None
        if rel:
            req = self.context.get("request")
            profile_image = rel if rel.startswith("http") or not req else req.build_absolute_uri(rel)

        # 제안글 집계(제안글 좋아요/스크랩)
        try:
            prop_likes_count = prop.proposer_like_proposal.count()
            prop_scraps_count = prop.proposer_scrap_proposal.count() + prop.founder_scrap_proposal.count()
        except Exception:
            prop_likes_count = 0
            prop_scraps_count = 0

        # created_at → "방금 전/20분 전/…"로 변환
        humanized = HumanizedDateTimeField().to_representation(getattr(prop, "created_at", None))

        return {
            "id": prop.id,
            "industry": prop.get_industry_display(),
            "title": prop.title,
            "content": prop.content,
            "business_hours": prop.business_hours,
            "address": prop.address,
            "radius": getattr(prop, "get_radius_display", lambda: "")(),
            "image": images,
            "user": {"name": masked_name, "profile_image": profile_image},  # ← 함수 쓰지 말고 인라인
            "created_at": humanized,
            "likes_count": prop_likes_count,    # ← 제안글 집계
            "scraps_count": prop_scraps_count,  # ← 제안글 집계
        }

    # 상세에서는 founder 블록에 description도 포함
    def get_founder(self, obj):
        base = super().get_founder(obj)
        base["description"] = obj.founder_description
        return base
    
    def to_representation(self, instance):
        data = super().to_representation(instance)

        # business_hours 오전/오후 포맷 (제안글 상세와 동일 포맷)
        bh = instance.business_hours or {}
        for key in ("start", "end"):
            val = bh.get(key)
            if isinstance(val, str) and ":" in val:
                try:
                    hour, minute = map(int, val.split(":"))
                    h12 = hour % 12 or 12
                    ap = "오전" if hour < 12 else "오후"
                    bh[key] = f"{ap} {h12}시"
                except Exception:
                    pass
        data["business_hours"] = bh

        profile = (self.context.get("profile") or "").lower()
        if profile == "founder":
            # 명세: founder 응답에는 is_liked 불포함
            data.pop("is_liked", None)
        return data
    
    def get_status(self, obj):
        # choices의 display(예: '진행 중') 반환
        return obj.get_status_display()


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
        
class ProposerFundingRewardItemSerializer(serializers.Serializer):
    id = serializers.CharField()                 # ProposerReward.id (nanoid)
    category = serializers.CharField()           # Reward.get_category_display()
    business_name = serializers.CharField(allow_null=True)
    title = serializers.CharField()
    content = serializers.CharField()
    amount = serializers.IntegerField()

class ProposerLevelRewardItemSerializer(serializers.Serializer):
    id = serializers.CharField()                 # ProposerReward.id (nanoid)
    category = serializers.CharField()           # "레벨"
    title = serializers.CharField()
    content = serializers.CharField()
    amount = serializers.IntegerField()
