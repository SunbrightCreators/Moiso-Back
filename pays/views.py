from django.shortcuts import render

# Create your views here.
import base64
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.conf import settings 
import os

from .models import Payment, Cancel
from .serializers import PaymentSerializer


class ConfirmPaymentAPIViewRoot(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        try:
            paymentKey = request.data.get('paymentKey')
            orderId = request.data.get('orderId')
            amount = request.data.get('amount')

            # Toss 시크릿 키 base64 인코딩
            widget_secret_key = os.environ.get("TOSS_SECRET_KEY")
            encoded_secret_key = base64.b64encode(f"{widget_secret_key}:".encode()).decode()

            toss_response = requests.post(
                "https://api.tosspayments.com/v1/payments/confirm",

                headers = {
                "Authorization": f"Basic {encoded_secret_key}",
                "Content-Type": "application/json",
                },

                json={
                    "paymentKey": paymentKey,
                    "orderId": orderId,
                    "amount": amount
                }
            )

            if toss_response.status_code == 200:
                data = toss_response.json()

                # 결제 정보 저장
                payment = Payment.objects.create(
                    payment_key=data['paymentKey'], # 필수
                    order_id=data['orderId'],       # 필수
                    amount=data['totalAmount'],
                    method=data['method'],
                    card_company=data.get('card', {}).get('company'),
                    card_number=data.get('card', {}).get('number'),
                    approved_at=data['approvedAt'],
                    currency=data['currency'],
                )
                return Response(PaymentSerializer(payment).data, status=200)
            return Response(toss_response.json(), status=toss_response.status_code) # 토스에게 받은 응답을 클라이언트에게 전달

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 
        

class CancelPaymentAPIViewRoot(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        try:
            payment_key = request.data.get("paymentKey")
            cancel_reason = request.data.get("cancelReason", "고객 요청")  # 필수!

            # Toss 시크릿 키 base64 인코딩
            widget_secret_key = os.environ.get("TOSS_SECRET_KEY")
            encoded_secret_key = base64.b64encode(f"{widget_secret_key}:".encode()).decode()

            toss_response = requests.post(
                f"https://api.tosspayments.com/v1/payments/{payment_key}/cancel",
                headers={
                    "Authorization": f"Basic {encoded_secret_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "cancelReason": cancel_reason
                }
            )

            if toss_response.status_code == 200:
                data = toss_response.json()

                # 결제 취소 정보 DB에 저장
                payment = Payment.objects.get(payment_key=payment_key)
                for cancel in data.get("cancels", []):
                    Cancel.objects.create(
                        payment=payment,
                        cancel_amount=cancel.get("cancelAmount"),
                        canceled_at=cancel.get("canceledAt"),
                        cancel_status=cancel.get("cancelStatus"),
                        transaction_key=cancel.get("transactionKey"),
                        eceipt_key=cancel.get("receiptKey"),
                    )

                return Response(data, status=200)
            return Response(toss_response.json(), status=toss_response.status_code)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

