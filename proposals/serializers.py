from django.utils import timezone
from rest_framework import serializers
from utils.choices import IndustryChoices, RadiusChoices
from utils.serializer_fields import HumanizedDateTimeField
from .models import Proposal, ProposerLikeProposal
from accounts.models import ProposerLevel

# ── 생성용 ────────────────────────────────────────────────────────────────
class ProposalCreateSerializer(serializers.Serializer):
    title          = serializers.CharField(max_length=50)
    content        = serializers.CharField(max_length=1000)
    industry       = serializers.ChoiceField(choices=IndustryChoices.choices)
    business_hours = serializers.JSONField() 
    address        = serializers.JSONField() 
    position       = serializers.JSONField() 
    radius         = serializers.ChoiceField(choices=RadiusChoices.choices)

    def to_internal_value(self, data):
        # 멀티파트에서 문자열 JSON을 받아오는 경우를 처리
        import json
        def _clean(v): 
            return v.strip() if isinstance(v, str) else v
        def _maybe_json(v):
            v = _clean(v)
            if isinstance(v, str):
                try: 
                    return json.loads(v)
                except Exception: 
                    return v
            return v

        src = data  # QueryDict
        clean = {
            "title": _clean(src.get("title")),
            "content": _clean(src.get("content")),
            "industry": _clean(src.get("industry")),
            "business_hours": _maybe_json(src.get("business_hours")),
            "address": _maybe_json(src.get("address")),
            "position": _maybe_json(src.get("position")),
        }

        radius = _clean(src.get("radius"))
        try:
            clean["radius"] = int(radius)
        except Exception:
            clean["radius"] = radius

        return super().to_internal_value(clean)

class ProposalListSerializer(serializers.ModelSerializer):
    industry = serializers.SerializerMethodField()
    radius = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    created_at = HumanizedDateTimeField()
    likes_count = serializers.IntegerField()
    scraps_count = serializers.IntegerField()

    is_scrapped = serializers.BooleanField()
    is_liked = serializers.BooleanField()
    is_address  = serializers.BooleanField()

    class Meta:
        model = Proposal
        fields = ('id','industry','title','content','business_hours','address',
                  'radius','image','user','created_at','likes_count','scraps_count',
                  'is_liked','is_scrapped','is_address')

    def get_industry(self, obj):
        return obj.get_industry_display()

    def get_radius(self, obj):
        return obj.get_radius_display()

    def get_image(self, obj):
        request = self.context.get("request")
        images = []
        for f in (obj.image1, obj.image2, obj.image3):
            if not f:
                continue
            try:
                rel = f.url
            except Exception:
                rel = None
            if rel:
                images.append(request.build_absolute_uri(rel) if request else rel)
        return images

    def get_user(self, obj):
        request = self.context.get("request")
        u = obj.user.user

        # 이름 마스킹 (인라인)
        name = u.name
        if not name:
            masked = None
        elif len(name) == 1:
            masked = name + "*"
        else:
            masked = name[0] + "**"

        # 프로필 이미지 절대경로 (인라인)
        pi = getattr(u, "profile_image", None)
        if pi:
            try:
                rel = pi.url
            except Exception:
                rel = None
            profile_image = request.build_absolute_uri(rel) if (request and rel) else rel
        else:
            profile_image = None

        return {'name': masked, 'profile_image': profile_image}


# ── 지도(동 이하) 목록용 ─────────────────────────────────────────────────
class ProposalMapItemSerializer(ProposalListSerializer):
    position = serializers.SerializerMethodField()

    class Meta(ProposalListSerializer.Meta):
        fields = ProposalListSerializer.Meta.fields + ('position',)

    def get_position(self, obj: Proposal):
        pos = obj.position or {}
        return {"latitude": pos.get("latitude"), "longitude": pos.get("longitude")}
    
    # founder 모드일 때 is_liked 제거
    def to_representation(self, instance):
        data = super().to_representation(instance)
        profile = (self.context.get("profile") or "").lower()
        if profile == "founder":
            data.pop("is_liked", None)
        return data
    
class ProposalZoomFounderItemSerializer(ProposalListSerializer):
    has_funding = serializers.BooleanField()
    likes_analysis = serializers.SerializerMethodField()

    class Meta(ProposalListSerializer.Meta):
        fields = ProposalListSerializer.Meta.fields + ("has_funding", "likes_analysis")

    def get_likes_analysis(self, obj: Proposal):
        # ProposalDetailSerializer의 founder 분기와 동일 로직 (position 없이)
        addr = obj.address or {}
        total = getattr(obj, "likes_count", 0)
        local = (
            ProposerLikeProposal.objects
            .filter(
                proposal=obj,
                user__proposer_level__address__sido=addr.get("sido"),
                user__proposer_level__address__sigungu=addr.get("sigungu"),
                user__proposer_level__address__eupmyundong=addr.get("eupmyundong"),
            )
            .values("user_id").distinct().count()
        )
        stranger = max(total - local, 0)
        return {
            "local_count": local,
            "stranger_count": stranger,
            "local_ratio": f"{round((local/total)*100)}%" if total else "0%",
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # founder는 좋아요 불가 → is_liked 제거
        data.pop("is_liked", None)
        # business_hours 오전/오후 포맷 (position은 애초에 없음)
        bh = instance.business_hours or {}
        out_bh = {}
        for key in ("start", "end"):
            val = bh.get(key)
            if isinstance(val, str) and ":" in val:
                try:
                    hour, minute = map(int, val.split(":"))
                    out_bh[key] = f"{'오전' if hour < 12 else '오후'} {hour % 12 or 12}시"
                except Exception:
                    out_bh[key] = val
            else:
                out_bh[key] = val
        data["business_hours"] = out_bh
        return data


class ProposalDetailSerializer(ProposalMapItemSerializer):
    has_funding = serializers.BooleanField()

    class Meta(ProposalMapItemSerializer.Meta):
        fields = ProposalMapItemSerializer.Meta.fields + ("has_funding",)


    def get_user(self, obj: Proposal):
        base = super().get_user(obj)  # name/profile_image 재사용
        addr = obj.address or {}
        latest_level = (
            ProposerLevel.objects
            .filter(
                user=obj.user,
                address__sido=addr.get("sido"),
                address__sigungu=addr.get("sigungu"),
                address__eupmyundong=addr.get("eupmyundong"),
            )
            .order_by("-id")
            .values_list("level", flat=True)
            .first()
        ) or 0
        base["proposer_level"] = {
            "address": {
                "sido": addr.get("sido"),
                "sigungu": addr.get("sigungu"),
                "eupmyundong": addr.get("eupmyundong"),
            },
            "level": latest_level,
        }
        return base


    def to_representation(self, instance):
        data = super().to_representation(instance)

        bh = instance.business_hours or {}
        for key in ("start", "end"):
            val = bh.get(key)
            if isinstance(val, str) and ":" in val:
                try:
                    hour, minute = map(int, val.split(":"))
                    data["business_hours"][key] = f"{'오전' if hour < 12 else '오후'} {hour % 12 or 12}시"
                except Exception:
                    pass

        profile = (self.context.get("profile") or "").lower()
        if profile == "founder":
            data.pop("is_liked", None) # founder는 좋아요 불가 → 제거 유지
            addr = instance.address or {}  # founder 전용 likes_analysis
            total = data.get("likes_count", 0)
            local = (
                ProposerLikeProposal.objects
                .filter(
                    proposal=instance,
                    user__proposer_level__address__sido=addr.get("sido"),
                    user__proposer_level__address__sigungu=addr.get("sigungu"),
                    user__proposer_level__address__eupmyundong=addr.get("eupmyundong"),
                )
                .values("user_id").distinct().count()
            )
            stranger = max(total - local, 0)
            data["likes_analysis"] = {
                "local_count": local,
                "stranger_count": stranger,
                "local_ratio": f"{round((local/total)*100)}%" if total else "0%",
            }
        return data 
    

class ProposalMyCreatedItemSerializer(serializers.ModelSerializer):
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Proposal
        fields = ("id", "created_at", "title")

    def get_created_at(self, obj: Proposal) -> str:
        dt = timezone.localtime(obj.created_at)
        return dt.strftime("%Y.%m.%d.")

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

