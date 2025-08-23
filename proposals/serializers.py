from django.utils import timezone
from rest_framework import serializers
from utils.choices import IndustryChoices, RadiusChoices
from utils.serializer_fields import HumanizedDateTimeField
from fundings.models import Funding
from .models import Proposal
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


class ProposalDetailSerializer(ProposalMapItemSerializer):
    is_liked = serializers.SerializerMethodField()
    is_scrapped = serializers.SerializerMethodField()
    is_address = serializers.SerializerMethodField()
    has_funding = serializers.SerializerMethodField()

    class Meta(ProposalMapItemSerializer.Meta):
        fields = tuple(
            f for f in ProposalMapItemSerializer.Meta.fields if f != "is_address"
        ) + ("has_funding",)


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


    # --- is_* 계산 ---
    def get_is_liked(self, obj):
        request = self.context.get("request")
        profile = (self.context.get("profile") or "").lower()
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        if profile != "proposer":
            return False
        from .models import ProposerLikeProposal
        return ProposerLikeProposal.objects.filter(
            proposal=obj, user=request.user.proposer
        ).exists()

    def get_is_scrapped(self, obj):
        request = self.context.get("request")
        profile = (self.context.get("profile") or "").lower()
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        if profile == "proposer":
            from .models import ProposerScrapProposal
            return ProposerScrapProposal.objects.filter(
                proposal=obj, user=request.user.proposer
            ).exists()
        if profile == "founder":
            from .models import FounderScrapProposal
            return FounderScrapProposal.objects.filter(
                proposal=obj, user=request.user.founder
            ).exists()
        return False
    
    def to_representation(self, instance):
        data = super().to_representation(instance)

        # business_hours 오전/오후 포맷 (인라인, 원문 로직 유지)
        bh = instance.business_hours or {}
        for key in ("start", "end"):
            val = bh.get(key)
            if isinstance(val, str) and ":" in val:
                try:
                    hour, minute = map(int, val.split(':'))
                    h = hour  # 원문 'h' 사용 보존
                    bh[key] = f"{'오전' if hour < 12 else '오후'} {h % 12 or 12}시"
                except Exception:
                    pass
        data["business_hours"] = bh

        profile = (self.context.get("profile") or "").lower()

        if profile == "founder":
            # founder는 좋아요 불가 → 응답에서 필드 제거
            data.pop("is_liked", None)

            # founder 전용 likes_analysis 추가 (이 부분만 유지)
            from .models import ProposerLikeProposal
            addr = instance.address or {}
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

    def get_has_funding(self, obj: Proposal) -> bool:
        return Funding.objects.filter(proposal=obj).exists()
    

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

