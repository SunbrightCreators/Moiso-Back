from rest_framework import serializers
from .models import Payment, Cancel

class CancelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cancel
        fields = '__all__'

class PaymentSerializer(serializers.ModelSerializer):
    # 나의 결제(Payment)에 연결된 취소 내역(Cancel) 들을 배열 형태로 포함해서 응답에 보여줌
    cancels = CancelSerializer(many=True, read_only=True)  # related_name='cancels' 덕분에 자동 연결
    class Meta:
        model = Payment
        fields = '__all__'