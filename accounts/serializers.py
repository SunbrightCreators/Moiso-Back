from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User

class UserSignupSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    password = serializers.CharField(max_length=64, write_only=True)
    password2 = serializers.CharField(max_length=64, write_only=True, required=True)

    class Meta:
        model = User
        fields = ('id','first_name', 'last_name', 'gender', 'birth_year','email', 'password', 'password2',)
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {
                'required': True,
                'error_messages': {
                'required': '이메일은 필수 입력 항목입니다.',
                'blank': '이메일을 입력해주세요.',
                'invalid': '잘못된 유형의 이메일 주소입니다.',
                },
            }, 
        }

    def validate(self, data):
            if data.get('password') != data.get('password2'):
                raise serializers.ValidationError({'password2': '비밀번호가 일치하지 않습니다.'})
            return data


    def create(self, validated_data:dict):
        validated_data.pop('password2', None)
        password = validated_data.pop('password')  
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user
    
class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(
            email=data.get('email'),
            password=data.get('password')
        )
        if not user:
            raise serializers.ValidationError('이메일 또는 비밀번호가 올바르지 않습니다.')
        data['user'] = user
        return data
