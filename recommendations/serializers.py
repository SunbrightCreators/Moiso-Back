from proposals.serializers import ProposalListSerializer

# proposals/serializers.py (추가)
class ProposalCalcItemSerializer(ProposalListSerializer):
    def get_user(self, obj):
        # ProposalDetailSerializer.get_user()과 동일 로직 재사용
        base = super().get_user(obj)  # name/profile_image
        addr = obj.address or {}
        from accounts.models import ProposerLevel
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
        # founder는 좋아요 불가 → is_liked 제거 (다른 serializer들과 규칙 통일)
        profile = (self.context.get("profile") or "").lower()
        if profile == "founder":
            data.pop("is_liked", None)
        return data
