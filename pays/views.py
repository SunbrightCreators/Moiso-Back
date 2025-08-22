import secrets
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Payment, Order
from .serializers import CreateOrderSerializer, OrderResponseSerializer, ConfirmPaySerializer, CancelPaySerializer
from utils.choices import RewardCategoryChoices, OrderStatusChoices, PaymentStatusChoices
from fundings.models import Funding, Reward
from .services import toss_confirm, TossError, map_toss_to_payment_fields, shape_client_response, toss_cancel, shape_cancel_response

DONATION_UNIT = 1000
DRAFT_TTL_MIN = 15

def _gen_order_id(funding_id: int) -> str:
    ts = timezone.localtime().strftime("%Y%m%d%H%M%S")
    nonce = secrets.token_hex(4)
    return f"fund_{funding_id}_{ts}_{nonce}"

class PaysRoot(APIView):
    """
    POST /pays  — 주문(임시) 생성. 토스 승인 호출 X
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        # 1) 입력 검증
        ser = CreateOrderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        # 2) 유저/펀딩
        proposer = getattr(request.user, "proposer", None)
        if proposer is None:
            return Response({"detail": "proposer 프로필이 없습니다."}, status=status.HTTP_403_FORBIDDEN)

        funding = get_object_or_404(Funding, pk=v["funding_id"])

        # 3) items / level_reward 에 등장하는 모든 reward_id 조회
        item_ids  = [it["reward_id"] for it in v["items"]]
        level_ids = [it["reward_id"] for it in v.get("level_reward", [])]
        all_ids   = set(item_ids + level_ids)

        rewards_map = (
            Reward.objects
            .filter(id__in=all_ids, funding=funding)
            .in_bulk(field_name="id")
        )
        missing = [rid for rid in all_ids if rid not in rewards_map]
        if missing:
            return Response({"detail": f"유효하지 않은 reward_id 포함: {missing}"}, status=400)

        now = timezone.now()

        # 4) items 금액 계산 (LEVEL 금지)
        items_amount = 0
        items_json = []
        for it in v["items"]:
            r = rewards_map[it["reward_id"]]
            if r.category == RewardCategoryChoices.LEVEL:
                return Response({"detail": "LEVEL 리워드는 items에 담을 수 없습니다."}, status=400)
            if r.expired_at and r.expired_at <= now:
                return Response({"detail": f"리워드({r.id})가 만료되었습니다."}, status=400)

            unit = int(r.amount)
            qty  = int(it["quantity"])
            line = unit * qty
            items_amount += line
            items_json.append({
                "reward_id": r.id,
                "title": r.title,
                "unit_amount": unit,
                "quantity": qty,
                "line_total": line,
            })

        # 5) level_reward 할인 계산 (LEVEL만 허용)
        discount_amount = 0
        level_json = []
        for it in v.get("level_reward", []):
            r = rewards_map[it["reward_id"]]
            if r.category != RewardCategoryChoices.LEVEL:
                return Response({"detail": f"리워드({r.id})는 LEVEL이 아닙니다."}, status=400)
            if r.expired_at and r.expired_at <= now:
                return Response({"detail": f"레벨 리워드({r.id})가 만료되었습니다."}, status=400)

            unit = int(r.amount)
            qty  = int(it["quantity"])
            line = unit * qty
            discount_amount += line
            level_json.append({
                "reward_id": r.id,
                "title": r.title,
                "unit_amount": unit,
                "quantity": qty,
                "line_total": line,  # 할인 합산 근거
            })

        # 6) 기부 금액
        donation_qty    = int(v.get("donation_qty", 0))
        donation_amount = donation_qty * DONATION_UNIT

        # 7) 최종 금액 (0 하한)
        amount = max(items_amount + donation_amount - discount_amount, 0)

        # 8) order_id / 만료
        p = v["payment"]
        order_id = p.get("order_id") or _gen_order_id(funding.id)

        # 같은 order_id가 이미 있으면 본인/동일 펀딩일 때만 덮어쓰기 (idempotent)
        order, _created = Order.objects.select_for_update().get_or_create(
            order_id=order_id,
            defaults={"funding": funding, "user": proposer}
        )
        
        if order.user_id != proposer.id or order.funding_id != funding.id:
            return Response({"detail": "이미 사용 중인 order_id 입니다."}, status=409)

        expires_at = p.get("expires_at") or (timezone.now() + timedelta(minutes=DRAFT_TTL_MIN))

        # 9) 저장
        order.items_json         = items_json
        order.level_rewards_json = level_json
        order.donation_qty       = donation_qty

        order.items_amount     = items_amount
        order.discount_amount  = discount_amount
        order.donation_amount  = donation_amount
        order.amount           = amount
        order.currency         = p.get("currency", "KRW")

        order.method      = p.get("method") or None
        order.success_url = p["success_url"]
        order.fail_url    = p["fail_url"]
        order.expires_at  = expires_at
        order.status      = OrderStatusChoices.PENDING
        order.save()

        # 10) 응답 (클라가 위젯 호출에 사용)
        resp = {
            "detail": "주문이 생성되었습니다. 펀딩 결제로 넘어갑니다",
            "order_id": order_id,
            "amount": amount,
            "currency": order.currency,
            "expires_at": order.expires_at,
        }
        return Response(OrderResponseSerializer(resp).data, status=200)
    
class PaysConfirm(APIView):
    """
    POST /pays/confirm
    - 위젯 성공 리다이렉트에서 받은 paymentKey/orderId/amount 를 받아
      토스 /v1/payments/confirm 호출 → Payment 저장 → 요약 응답
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        s = ConfirmPaySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        payment_key = s.validated_data["paymentKey"]
        order_id    = s.validated_data["orderId"]
        amount_in   = s.validated_data["amount"]

        # 1) Order 검증 (본인/금액/만료)
        order = get_object_or_404(Order, order_id=order_id)
        proposer = getattr(request.user, "proposer", None)
        if proposer is None or order.user_id != proposer.id:
            return Response({"detail": "주문 소유주가 아닙니다."}, status=status.HTTP_403_FORBIDDEN)

        if timezone.now() > order.expires_at:
            order.status = OrderStatusChoices.EXPIRED
            order.save(update_fields=["status"])
            return Response({"detail": "주문이 만료되었습니다."}, status=status.HTTP_410_GONE)

        if int(amount_in) != int(order.amount):
            return Response({"detail": "금액 불일치: 서버 금액과 다릅니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 같은 펀딩에 동일 유저가 이미 Payment 있으면 차단(해커톤 정책)
        if Payment.objects.filter(funding=order.funding, user=order.user).exists():
            return Response({"detail": "이미 이 펀딩에 후원 완료된 기록이 있습니다."}, status=status.HTTP_409_CONFLICT)

        # 2) 토스 승인 호출
        try:
            toss = toss_confirm(payment_key, order_id, amount_in)
        except TossError as e:
            # 토스 에러 메시지 그대로 전달(가능하면 코드도)
            return Response({"detail": e.payload.get("message") or str(e), "code": e.payload.get("code")}, status=e.payload.get("status", 400))

        # 3) Payment 저장(매핑)
        pf = map_toss_to_payment_fields(toss)
        pay = Payment(
            order=order,
            payment_key=pf["payment_key"],
            funding=order.funding,
            user=order.user,
            version=pf["version"],
            type=pf["type"],
            order_id=pf["order_id"],
            order_name=pf["order_name"],
            m_id=pf["m_id"],
            currency=pf["currency"],
            method=pf["method"],
            total_amount=pf["total_amount"],
            balance_amount=pf["balance_amount"],
            status=pf["status"],
            requested_at=pf["requested_at"],
            approved_at=pf["approved_at"],
            use_escrow=pf["use_escrow"],
            last_transaction_key=pf["last_transaction_key"],
            supplied_amount=pf["supplied_amount"],
            vat=pf["vat"],
            culture_expense=pf["culture_expense"],
            tax_free_amount=pf["tax_free_amount"],
            tax_exemption_amount=pf["tax_exemption_amount"],
            is_partial_cancelable=pf["is_partial_cancelable"],
            receipt=pf["receipt"],
            checkout=pf["checkout"],
            easy_pay=pf["easy_pay"],
            country=pf["country"],
            failure=pf["failure"],
            discount=pf["discount"],
            card=pf["card"],
            virtual_account=pf["virtual_account"],
            mobile_phone=pf["mobile_phone"],
            gift_certificate=pf["gift_certificate"],
            transfer=pf["transfer"],
            # 편의 필드(리포팅) — 주문 스냅샷에서 복사
            items_amount=order.items_amount,
            discount_amount=order.discount_amount,
            donation_amount=order.donation_amount,
        )
        pay.save()

        # 4) Order 상태 갱신
        if pay.method == "가상계좌":
            # 입금 대기 → 주문은 계속 진행 중으로 둔다.
            order.status = OrderStatusChoices.PENDING
        else:
            # 즉시 승인 → 주문 확정
            order.status = OrderStatusChoices.CONFIRMED
        order.save(update_fields=["status"])

        # 5) 클라 응답(명세 형태)
        body = shape_client_response(pay, toss)
        return Response(body, status=status.HTTP_200_OK)
    
class PaysCancel(APIView):
    """
    POST /pays/{payment_key}/cancel
    - 결제(카드/간편/계좌이체/가상계좌)를 취소/환불
    - 가상계좌:
        * 입금 전: 환불계좌 불필요(취소금액 0으로 처리됨)
        * 입금 후: refund_account 필수(원금 환불)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, payment_key: str):
        # 0) 바디 검증
        s = CancelPaySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        refund = v.get("refund_account")

        # 1) 결제 객체 조회 + 소유권 확인
        pay = get_object_or_404(Payment, pk=payment_key)
        proposer = getattr(request.user, "proposer", None)
        if (proposer is None) or (pay.user_id != proposer.id):
            return Response({"detail": "결제 소유주가 아닙니다."}, status=status.HTTP_403_FORBIDDEN)

        # 이미 취소된 건?
        if pay.status in (PaymentStatusChoices.CANCELED, PaymentStatusChoices.PARTIAL_CANCELED):
            return Response({"detail": "이미 취소 처리된 결제입니다."}, status=status.HTTP_409_CONFLICT)

        # 2) 토스 취소 페이로드 구성
        # 전체 취소(우리 정책) → balance_amount 만큼 취소
        payload = {
            "cancelReason": v["cancel_reason"],
            "cancelAmount": int(pay.balance_amount),
        }

        # 가상계좌 처리 분기
        is_va = (pay.method == "가상계좌")
        if is_va:
            # 입금 전: 토스가 0원 취소로 처리 → refund 계좌 불필요
            if pay.status == PaymentStatusChoices.WAITING_FOR_DEPOSIT:
                payload["cancelAmount"] = 0
            else:
                # 입금 후: 환불 계좌 필수
                if not refund:
                    return Response({"detail": "가상계좌 ‘입금 후’ 환불은 refund_account가 필요합니다."},
                                    status=status.HTTP_400_BAD_REQUEST)
                payload["refundReceiveAccount"] = {
                    "bank":          refund["bank"],
                    "accountNumber": refund["account_number"],
                    "holderName":    refund["holder_name"],
                }

        # 3) 토스 취소 호출
        try:
            toss = toss_cancel(pay.payment_key, payload)
        except TossError as e:
            return Response(
                {"detail": e.payload.get("message") or str(e), "code": e.payload.get("code")},
                status=e.payload.get("status", 400)
            )

        # 4) 로컬 상태 업데이트 (토스 응답 반영)
        #   - 전액 취소라면 CANCELED
        #   - 부분 취소가 내려오는 케이스는 현재 스키마(OneToOne Cancel)상 정책적으로 미사용
        # 토스 응답의 balanceAmount/ status 로 업데이트
        pay.balance_amount = int(toss.get("balanceAmount") or 0)
        pay.status = toss.get("status") or PaymentStatusChoices.CANCELED
        pay.save(update_fields=["balance_amount", "status"])

        # 5) 응답 바디(명세) 가공
        body = shape_cancel_response(pay, toss)
        return Response(body, status=status.HTTP_200_OK)
