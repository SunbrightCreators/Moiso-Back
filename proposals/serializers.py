from django.utils import timezone
from rest_framework import serializers
from utils.choices import IndustryChoices, RadiusChoices
from utils.serializer_fields import HumanizedDateTimeField
from .models import Proposal, ProposerLikeProposal, ProposerScrapProposal, FounderScrapProposal
from accounts.models import ProposerLevel


def _label(choices_cls, value):
    return dict(choices_cls.choices).get(value, str(value))

def _abs_url(request, file_field):
    if not file_field:
        return None
    try:
        rel = file_field.url
    except Exception:
        return None
    return request.build_absolute_uri(rel) if request else rel

def _mask_name(name: str | None):
    if not name:
        return None
    if len(name) == 1:
        return name + "*"
    return name[0] + "**"

def _format_ampm(hhmm: str | None):
    # "09:00" -> "오전 9시", "18:00" -> "오후 6시"
    if not hhmm or len(hhmm) < 4 or ":" not in hhmm:
        return hhmm
    try:
        h = int(hhmm.split(":")[0])
    except Exception:
        return hhmm
    period = "오전" if h < 12 else "오후"
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    return f"{period} {h12}시"


# ── 공용 서브 시리얼라이저 ──────────────────────────────────────────────
class BusinessHoursSerializer(serializers.Serializer):
    start = serializers.RegexField(r"^\d{2}:\d{2}$")
    end   = serializers.RegexField(r"^\d{2}:\d{2}$")

class AddressSerializer(serializers.Serializer):
    sido         = serializers.CharField()
    sigungu      = serializers.CharField()
    eupmyundong  = serializers.CharField()
    jibun_detail = serializers.CharField()
    road_detail  = serializers.CharField()

class PositionSerializer(serializers.Serializer):
    latitude  = serializers.FloatField()
    longitude = serializers.FloatField()


# ── 생성용 ────────────────────────────────────────────────────────────────
class ProposalCreateSerializer(serializers.Serializer):
    title          = serializers.CharField(max_length=50)
    content        = serializers.CharField(max_length=1000)
    industry       = serializers.ChoiceField(choices=IndustryChoices.choices)
    business_hours = BusinessHoursSerializer()
    address        = AddressSerializer()
    position       = PositionSerializer()
    radius         = serializers.ChoiceField(choices=RadiusChoices.choices)
    # 파일: view에서 request.FILES.getlist('image') 처리


# ── 지도(동 이하) 목록용 ─────────────────────────────────────────────────
class ProposalMapItemSerializer(serializers.ModelSerializer):
    position     = serializers.SerializerMethodField()
    created_at   = HumanizedDateTimeField()
    user         = serializers.SerializerMethodField()
    industry     = serializers.SerializerMethodField()
    radius       = serializers.SerializerMethodField()
    image        = serializers.SerializerMethodField()
    likes_count  = serializers.IntegerField()
    scraps_count = serializers.IntegerField()

    class Meta:
        model  = Proposal
        fields = (
            "id",
            "position",
            "created_at",
            "title",
            "content",
            "user",
            "industry",
            "business_hours",
            "address",
            "radius",
            "image",
            "likes_count",
            "scraps_count",
        )

    def get_position(self, obj: Proposal):
        pos = obj.position or {}
        return {"latitude": pos.get("latitude"), "longitude": pos.get("longitude")}

    def get_user(self, obj: Proposal):
        request = self.context.get("request")
        account_user = getattr(obj.user, "user", None)
        name = getattr(account_user, "name", None)
        profile_image = _abs_url(request, getattr(account_user, "profile_image", None))
        return {"name": _mask_name(name), "profile_image": profile_image}

    def get_industry(self, obj: Proposal):
        return _label(IndustryChoices, obj.industry)

    def get_radius(self, obj: Proposal):
        return _label(RadiusChoices, obj.radius)

    def get_image(self, obj: Proposal):
        request = self.context.get("request")
        urls = []
        for f in (obj.image1, obj.image2, obj.image3):
            u = _abs_url(request, f)
            if u:
                urls.append(u)
        return urls


# ── 상세용 ────────────────────────────────────────────────────────────────
class ProposalDetailSerializer(serializers.ModelSerializer):
    image          = serializers.SerializerMethodField()
    industry       = serializers.SerializerMethodField()
    created_at     = serializers.SerializerMethodField()         # "YYYY.MM.DD. HH:MM" (KST)
    user           = serializers.SerializerMethodField()         # 이름 마스킹 + 최신 지역 레벨
    business_hours = serializers.SerializerMethodField()         # "오전/오후 N시"
    radius         = serializers.SerializerMethodField()
    position       = serializers.SerializerMethodField()
    likes_count    = serializers.SerializerMethodField()
    scraps_count   = serializers.SerializerMethodField()

    class Meta:
        model  = Proposal
        fields = (
            "id",
            "image",
            "industry",
            "title",
            "created_at",
            "user",
            "content",
            "business_hours",
            "address",
            "radius",
            "position",
            "likes_count",
            "scraps_count",
            # founder일 때만 to_representation에서 likes_analysis 추가
        )

    # ---- basics ----
    def get_image(self, obj: Proposal):
        request = self.context.get("request")
        urls = []
        for f in (obj.image1, obj.image2, obj.image3):
            u = _abs_url(request, f)
            if u:
                urls.append(u)
        return urls

    def get_industry(self, obj: Proposal):
        return _label(IndustryChoices, obj.industry)

    def get_created_at(self, obj: Proposal):
        # ✅ 한국시간 기준으로 포맷
        dt = timezone.localtime(obj.created_at)
        return dt.strftime("%Y.%m.%d. %H:%M")

    def get_user(self, obj: Proposal):
        request = self.context.get("request")
        account_user = getattr(obj.user, "user", None)  # accounts.User
        name = getattr(account_user, "name", None)
        profile_image = _abs_url(request, getattr(account_user, "profile_image", None))

        # ✅ 제안글 주소 기준 "최신" 지역 레벨 (최근 id 또는 created_at)
        addr = obj.address or {}
        latest_level = (
            ProposerLevel.objects
            .filter(
                user=obj.user,
                address__sido=addr.get("sido"),
                address__sigungu=addr.get("sigungu"),
                address__eupmyundong=addr.get("eupmyundong"),
            )
            .order_by("-id")                # created_at이 있다면 "-created_at" 권장
            .values_list("level", flat=True)
            .first()
        )

        return {
            "name": _mask_name(name),
            "profile_image": profile_image,
            "proposer_level": {
                "address": {
                    "sido": addr.get("sido"),
                    "sigungu": addr.get("sigungu"),
                    "eupmyundong": addr.get("eupmyundong"),
                },
                "level": latest_level if latest_level is not None else 0,
            },
        }

    def get_business_hours(self, obj: Proposal):
        bh = obj.business_hours or {}
        return {"start": _format_ampm(bh.get("start")), "end": _format_ampm(bh.get("end"))}

    def get_radius(self, obj: Proposal):
        return _label(RadiusChoices, obj.radius)

    def get_position(self, obj: Proposal):
        pos = obj.position or {}
        return {"latitude": pos.get("latitude"), "longitude": pos.get("longitude")}

    # ---- counts ----
    def get_likes_count(self, obj: Proposal) -> int:
        return ProposerLikeProposal.objects.filter(proposal=obj).count()

    def get_scraps_count(self, obj: Proposal) -> int:
        return (
            ProposerScrapProposal.objects.filter(proposal=obj).count()
            + FounderScrapProposal.objects.filter(proposal=obj).count()
        )

    # ---- founder 전용 필드 주입 ----
    def to_representation(self, instance):
        data = super().to_representation(instance)
        profile = (self.context.get("profile") or "").lower()
        if profile == "founder":
            addr = instance.address or {}
            total = data.get("likes_count", 0)

            # 같은 제안자가 레벨 이력이 여러 개여도 1명으로 계산되도록 distinct(user_id)
            local = (
                ProposerLikeProposal.objects
                .filter(
                    proposal=instance,
                    user__proposer_level__address__sido=addr.get("sido"),
                    user__proposer_level__address__sigungu=addr.get("sigungu"),
                    user__proposer_level__address__eupmyundong=addr.get("eupmyundong"),
                )
                .values("user_id")
                .distinct()
                .count()
            )
            stranger = max(total - local, 0)
            ratio = f"{round((local / total) * 100)}%" if total else "0%"

            data["likes_analysis"] = {
                "local_count": local,
                "stranger_count": stranger,
                "local_ratio": ratio,
            }
        return data
    
class ProposalMyCreatedItemSerializer(serializers.ModelSerializer):
    """
    내가 작성한 제안글 목록 카드용 (요약 필드만)
    - created_at: 한국시간 기준 "YYYY.MM.DD." 포맷
    """
    created_at = serializers.SerializerMethodField()

    class Meta:
        model  = Proposal
        fields = ("id", "created_at", "title")

    def get_created_at(self, obj: Proposal) -> str:
        dt = timezone.localtime(obj.created_at)  # KST 보장 (settings.TIME_ZONE 사용)
        return dt.strftime("%Y.%m.%d.")
