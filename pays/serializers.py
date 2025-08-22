from rest_framework import serializers

class OrderItemSerializer(serializers.Serializer):
    reward_id = serializers.IntegerField()
    quantity  = serializers.IntegerField(min_value=1)

class LevelRewardItemSerializer(serializers.Serializer):
    reward_id = serializers.IntegerField()
    quantity  = serializers.IntegerField(min_value=1)

class OrderPaymentSerializer(serializers.Serializer):
    order_id    = serializers.CharField(max_length=64, required=False, allow_blank=True)
    amount      = serializers.IntegerField(min_value=0, required=False)   # 클라 제안값: 서버가 무시
    currency    = serializers.ChoiceField(choices=["KRW"], default="KRW")
    method      = serializers.CharField(required=False, allow_blank=True)
    success_url = serializers.URLField()
    fail_url    = serializers.URLField()
    expires_at  = serializers.DateTimeField(required=False)               # 선택, 없으면 서버가 +15분

class CreateOrderSerializer(serializers.Serializer):
    funding_id   = serializers.IntegerField()
    items        = OrderItemSerializer(many=True)
    donation_qty = serializers.IntegerField(min_value=0, required=False, default=0)
    level_reward = LevelRewardItemSerializer(many=True, required=False, default=[])
    payment      = OrderPaymentSerializer()

class OrderResponseSerializer(serializers.Serializer):
    detail     = serializers.CharField()
    order_id   = serializers.CharField()
    amount     = serializers.IntegerField()
    currency   = serializers.CharField()
    expires_at = serializers.DateTimeField()

class ConfirmPaySerializer(serializers.Serializer):
    paymentKey = serializers.CharField(max_length=200)
    orderId    = serializers.CharField(max_length=64)
    amount     = serializers.IntegerField(min_value=0)

class RefundAccountSerializer(serializers.Serializer):
    bank          = serializers.CharField(max_length=30)
    account_number = serializers.CharField(max_length=32)
    holder_name    = serializers.CharField(max_length=30)

class CancelPaySerializer(serializers.Serializer):
    cancel_reason  = serializers.CharField(max_length=200)
    refund_account = RefundAccountSerializer(required=False)

