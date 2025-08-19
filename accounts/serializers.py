from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from .models import User

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
