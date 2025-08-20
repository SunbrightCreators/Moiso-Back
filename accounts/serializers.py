from django.contrib.auth import authenticate, get_user_model, password_validation
from rest_framework import serializers

from utils.choices import SexChoices, IndustryChoices, FounderTargetChoices
from .models import Proposer, ProposerLevel, LocationHistory, Founder

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "password",
            "is_marketing_allowed",
            "name",
            "birth",
            "sex",
            "profile_image",
        )
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data:dict):
        password = validated_data.pop('password')
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            username=email,  
            password=password,
        )

        if not user:
            raise serializers.ValidationError(
                {"detail": "이메일 또는 비밀번호가 일치하지 않습니다."},
                code="authorization",
            )
        if not user.is_active:
            raise serializers.ValidationError(
                {"detail": "비활성화된 계정입니다."},
                code="inactive",
            )

        attrs["user"] = user
        return attrs


class JwtRefreshRequestSerializer(serializers.Serializer):
    grant_type = serializers.CharField(allow_null=False, allow_blank=False)
    refresh_token = serializers.CharField(allow_null=False, allow_blank=False)


# ── 공통 서브 시리얼라이저 ────────────────────────────────────────────────
class AddressSerializer(serializers.Serializer):
    sido = serializers.CharField()
    sigungu = serializers.CharField()
    eupmyundong = serializers.CharField()


class BusinessHoursSerializer(serializers.Serializer):
    start = serializers.RegexField(r"^\d{2}:\d{2}$")  # "HH:MM"
    end = serializers.RegexField(r"^\d{2}:\d{2}$")


# ── Proposer: ModelSerializer (주소는 write_only로 받아 부수처리) ───────────
class ProposerSerializer(serializers.ModelSerializer):
    # 모델엔 address 필드가 없으므로 최초 레벨/히스토리 기록용으로만 받음
    address = AddressSerializer(many=True, required=False, write_only=True)

    # industry는 List[Choice] 라고 가정
    industry = serializers.ListField(
        child=serializers.ChoiceField(choices=IndustryChoices.choices)
    )

    class Meta:
        model = Proposer
        fields = ("id", "user", "industry", "address")
        extra_kwargs = {
            "user": {"read_only": True},  # user는 context로 주입
        }

    def create(self, validated_data):
        addr_list = validated_data.pop("address", [])
        user = self.context["user"]                     # ← 컨텍스트에서 주입
        proposer = Proposer.objects.create(user=user, **validated_data)

        # 주소가 있으면 최초 레벨/히스토리 기록
        if addr_list:
            first_addr = addr_list[0]
            ProposerLevel.objects.create(user=proposer, level=1, address=first_addr)
            LocationHistory.objects.create(user=proposer, address=first_addr)
        return proposer


# ── Founder: ModelSerializer ───────────────────────────────────────────────
class FounderSerializer(serializers.ModelSerializer):
    address = AddressSerializer(many=True, required=False)
    industry = serializers.ListField(
        child=serializers.ChoiceField(choices=IndustryChoices.choices)
    )
    target = serializers.ListField(
        child=serializers.ChoiceField(choices=FounderTargetChoices.choices)
    )
    business_hours = BusinessHoursSerializer()

    class Meta:
        model = Founder
        fields = ("id", "user", "industry", "address", "target", "business_hours")
        extra_kwargs = {
            "user": {"read_only": True},  # user는 context로 주입
        }

    def validate_address(self, v):
        # 모델 제한(size=2) 가정 → 최대 2개만 허용
        return (v or [])[:2]

    def create(self, validated_data):
        user = self.context["user"]                     # ← 컨텍스트에서 주입
        return Founder.objects.create(user=user, **validated_data)


# ── 사용자 공통 필드 ────────────────────────────────────────────────────────
class UserBaseSignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    name = serializers.CharField(max_length=10)
    birth = serializers.RegexField(r"^\d{6}$")  # YYMMDD
    sex = serializers.ChoiceField(choices=SexChoices.choices)
    is_marketing_allowed = serializers.BooleanField(required=False, default=False)

    def validate_email(self, v):
        if User.objects.filter(email__iexact=v).exists():
            # 뷰에서 409로 변환
            raise serializers.ValidationError("이미 존재하는 이메일입니다.")
        return v

    def validate(self, attrs):
        password_validation.validate_password(attrs["password"])
        return attrs


# ── 모드별 회원가입 Serializer (User + 각 ModelSerializer 사용) ────────────
class UserProposerSignupSerializer(UserBaseSignupSerializer):
    # 요청 바디는 기존처럼 proposer_profile을 사용
    proposer_profile = serializers.DictField()

    def create(self, validated_data):
        # 1) User 생성 (UserSerializer 사용)
        proposer_payload = validated_data.pop("proposer_profile", {})
        user_ser = UserSerializer(data=validated_data, context=self.context)
        user_ser.is_valid(raise_exception=True)
        user = user_ser.save()

        # 2) Proposer 생성 (ProposerSerializer 사용)
        prop_ser = ProposerSerializer(
            data={
                "industry": proposer_payload.get("industry"),
                "address": proposer_payload.get("address", []),
            },
            context={**self.context, "user": user},
        )
        prop_ser.is_valid(raise_exception=True)
        prop_ser.save()

        return user


class UserFounderSignupSerializer(UserBaseSignupSerializer):
    founder_profile = serializers.DictField()

    def create(self, validated_data):
        # 1) User 생성
        founder_payload = validated_data.pop("founder_profile", {})
        user_ser = UserSerializer(data=validated_data, context=self.context)
        user_ser.is_valid(raise_exception=True)
        user = user_ser.save()

        # 2) Founder 생성 (FounderSerializer 사용)
        founder_ser = FounderSerializer(
            data={
                "industry": founder_payload.get("industry"),
                "address": founder_payload.get("address", []),
                "target": founder_payload.get("target"),
                "business_hours": founder_payload.get("business_hours", {}),
            },
            context={**self.context, "user": user},
        )
        founder_ser.is_valid(raise_exception=True)
        founder_ser.save()

        return user
