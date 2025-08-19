from django.contrib.auth import authenticate, get_user_model, password_validation
from rest_framework import serializers
from .models import User
from utils.choices import *

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'password',
            'is_marketing_allowed',
            'name',
            'birth',
            'sex',
            'profile_image',
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


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        # Django 기본 ModelBackend는 파라미터명이 username 이라서 이렇게 넘겨야 확실함
        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )

        if not user:
            # 와이어프레임의 문구와 맞춤
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
    
class AccessTokenRefreshSerializer(serializers.Serializer):
    grant_type = serializers.CharField(allow_null=False, allow_blank=False)
    refresh_token = serializers.CharField(allow_null=False, allow_blank=False)


# ── 공통 서브 시리얼라이저들 ────────────────────────────────────────────────
class AddressSerializer(serializers.Serializer):
    sido = serializers.CharField()
    sigungu = serializers.CharField()
    eupmyundong = serializers.CharField()

class BusinessHoursSerializer(serializers.Serializer):
    start = serializers.RegexField(r"^\d{2}:\d{2}$")  # "HH:MM"
    end   = serializers.RegexField(r"^\d{2}:\d{2}$")

# ── 프로필 페이로드 ────────────────────────────────────────────────────────
class ProposerProfileSerializer(serializers.Serializer):
    industry = serializers.ListField(
        child=serializers.ChoiceField(choices=IndustryChoices.choices),
        allow_empty=False,
        max_length=3,
        min_length=1,
    )
    # 와이어의 address는 Proposer 모델엔 없으므로 참고로 받아서
    # ProposerLevel/LocationHistory에 첫 주소를 기록
    address = AddressSerializer(many=True, required=False)  # [ {sido, ...} ]

class FounderProfileSerializer(serializers.Serializer):
    industry = serializers.ListField(
        child=serializers.ChoiceField(choices=IndustryChoices.choices),
        allow_empty=False,
        max_length=3,
        min_length=1,
    )
    address = AddressSerializer(many=True, required=False)  # 최대 2개만 사용
    target = serializers.ListField(
        child=serializers.ChoiceField(choices=FounderTargetChoices.choices),
        allow_empty=False,
        max_length=2,
        min_length=1,
    )
    business_hours = BusinessHoursSerializer()

# ── 사용자 공통 필드 ────────────────────────────────────────────────────────
class BaseSignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    name = serializers.CharField(max_length=10)
    birth = serializers.RegexField(r"^\d{6}$")  # YYMMDD
    sex = serializers.ChoiceField(choices=SexChoices.choices)
    is_marketing_allowed = serializers.BooleanField(required=False, default=False)

    def validate_email(self, v):
        if User.objects.filter(email__iexact=v).exists():
            # 409로 내려주기 위해 뷰에서 잡아줄 것
            raise serializers.ValidationError("이미 존재하는 이메일입니다.")
        return v

    def validate(self, attrs):
        password_validation.validate_password(attrs["password"])
        return attrs

# ── 모드별 시리얼라이저 ───────────────────────────────────────────────────
class ProposerSignupSerializer(BaseSignupSerializer):
    proposer_profile = ProposerProfileSerializer()

class FounderSignupSerializer(BaseSignupSerializer):
    founder_profile = FounderProfileSerializer()

