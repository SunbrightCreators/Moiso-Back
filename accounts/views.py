from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserSignupSerializer, UserLoginSerializer
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

# Create your views here.


class SignUpViewRoot(APIView):
  def post(self,request):
    serializer = UserSignupSerializer(data = request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'message': '회원가입이 완료되었습니다.'}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
  
class LoginViewRoot(APIView):
   def post(self, request):
      serializer = UserLoginSerializer(data=request.data)

      if serializer.is_valid():
            user = serializer.validated_data.get('user')
            refresh = RefreshToken.for_user(user)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                }
            },status=status.HTTP_200_OK)
      
      return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
  

