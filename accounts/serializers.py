from rest_framework import serializers
from .models import User

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
