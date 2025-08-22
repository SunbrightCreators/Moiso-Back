import base64
import requests
from django.conf import settings
from django.utils.dateparse import parse_datetime

TOSS_API_BASE = getattr(settings, "TOSS_API_BASE", "https://api.tosspayments.com")

def _auth_header():
    secret = settings.TOSS_SECRET_KEY  # 예: "test_sk_XXXX"
    token = base64.b64encode(f"{secret}:".encode()).decode()
    return {"Authorization": f"Basic {token}"}

def toss_confirm(payment_key: str, order_id: str, amount: int) -> dict:
    url = f"{TOSS_API_BASE}/v1/payments/confirm"
    headers = {
        "Content-Type": "application/json",
        **_auth_header(),
    }
    payload = {
        "paymentKey": payment_key,
        "orderId": order_id,
        "amount": amount,
    }
    r = requests.post(url, json=payload, headers=headers, timeout=10)
    # 토스는 4xx/5xx 시에도 JSON 바디로 에러를 내려줌
    try:
        data = r.json()
    except Exception:
        r.raise_for_status()
        # 여기 오기 어렵지만 안전망
        raise
    if r.status_code >= 400:
        # data 예: {"message":"...", "code":"...", "status":400}
        raise TossError(data.get("message") or "Toss confirm failed", data)

    return data

class TossError(Exception):
    def __init__(self, msg, payload=None):
        super().__init__(msg)
        self.payload = payload or {}

def _auth_header():
    """
    토스 비밀키를 Basic Base64("{SECRET}:") 로 인코딩.
    예) test_gsk_xxx 혹은 test_sk_xxx 모두 가능. 뒤 콜론(:) 반드시 포함.
    """
    secret = settings.TOSS_SECRET_KEY  # .env(.base)에 보관
    token = base64.b64encode(f"{secret}:".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def map_toss_to_payment_fields(toss: dict) -> dict:
    """토스 응답을 Payment 모델 필드로 매핑(누락키는 안전하게 기본값)"""
    # 공통
    out = {
        "payment_key":       toss.get("paymentKey"),
        "version":           toss.get("version") or "2022-11-16",
        "type":              toss.get("type") or "NORMAL",
        "order_id":          toss.get("orderId"),
        "order_name":        toss.get("orderName") or "",
        "m_id":              toss.get("mId") or "",
        "currency":          toss.get("currency") or "KRW",
        "method":            toss.get("method"),  # '카드'/'가상계좌'/...
        "total_amount":      int(toss.get("totalAmount") or 0),
        "balance_amount":    int(toss.get("balanceAmount") or 0),
        "status":            toss.get("status") or "DONE",
        "use_escrow":        bool(toss.get("useEscrow") or False),
        "last_transaction_key": toss.get("lastTransactionKey"),
        "supplied_amount":   int(toss.get("suppliedAmount") or 0),
        "vat":               int(toss.get("vat") or 0),
        "culture_expense":   bool(toss.get("cultureExpense") or False),
        "tax_free_amount":   int(toss.get("taxFreeAmount") or 0),
        "tax_exemption_amount": int(toss.get("taxExemptionAmount") or 0),
        "is_partial_cancelable": bool(toss.get("isPartialCancelable") or True),
        "receipt":           toss.get("receipt") or {},
        "checkout":          toss.get("checkout") or {},
        "easy_pay":          toss.get("easyPay") or {},
        "country":           toss.get("country"),
        "failure":           toss.get("failure") or {},
        "discount":          toss.get("discount") or {},
        # 시간
        "requested_at": parse_datetime(toss.get("requestedAt")) if toss.get("requestedAt") else None,
        "approved_at":  parse_datetime(toss.get("approvedAt"))  if toss.get("approvedAt")  else None,
        # 수단별
        "card":            toss.get("card") or {},
        "virtual_account": toss.get("virtualAccount") or {},
        "mobile_phone":    toss.get("mobilePhone") or {},
        "gift_certificate":toss.get("giftCertificate") or {},
        "transfer":        toss.get("transfer") or {},
        # 메타
        "metadata": toss.get("metadata") or {},
    }
    return out

def shape_client_response(payment_obj, toss: dict) -> dict:
    """명세에 맞춰 클라이언트로 돌려줄 바디 생성"""
    base = {
        "payment": {
            "id":           str(payment_obj.pk),  # 우리 PK는 payment_key라 중복이지만 명세에 맞춰 유지
            "payment_key":  payment_obj.payment_key,
            "order_id":     payment_obj.order_id,
            "method":       payment_obj.method,
            "status":       payment_obj.status,
            "amount":       payment_obj.total_amount,
            "currency":     payment_obj.currency,
            "approved_at":  payment_obj.approved_at.isoformat() if payment_obj.approved_at else None,
            # cancelable_until 은 토스 표준 응답에 고정 키가 없어 생략(있다면 toss에서 뽑아 추가하면 됨)
        }
    }

    # 방법별 부가 섹션
    if payment_obj.method == "가상계좌" and toss.get("virtualAccount"):
        va = toss["virtualAccount"]
        base["virtual_account"] = {
            "bank":           va.get("bank"),
            "account_number": va.get("accountNumber"),
            "holder":         va.get("customerName"),
            "due_date":       va.get("dueDate"),
        }
    elif toss.get("card"):
        c = toss["card"]
        base["card"] = {
            "issuer_code":              c.get("issuerCode"),
            "acquirer_code":            c.get("acquirerCode"),
            "number_masked":            c.get("number"),
            "installment_plan_months":  c.get("installmentPlanMonths"),
            "is_interest_free":         c.get("isInterestFree"),
            "approve_no":               c.get("approveNo"),
            "card_type":                c.get("cardType"),
            "owner_type":               c.get("ownerType"),
            "amount":                   c.get("amount"),
        }
    elif toss.get("transfer"):
        base["transfer"] = toss["transfer"]
    elif toss.get("mobilePhone"):
        base["mobile_phone"] = toss["mobilePhone"]

    return base

def toss_cancel(payment_key: str, payload: dict) -> dict:
    """
    POST /v1/payments/{paymentKey}/cancel
    payload 예:
    {
      "cancelReason": "사용자 취소",
      "cancelAmount": 28000,           # 전체/부분, 전체면 balanceAmount 사용 권장
      "refundReceiveAccount": {        # VA(입금 후) 환불에 필수
        "bank": "KB",
        "accountNumber": "1234567890",
        "holderName": "홍길동"
      }
    }
    """
    url = f"{TOSS_API_BASE}/v1/payments/{payment_key}/cancel"
    headers = {
        "Content-Type": "application/json",
        **_auth_header(),
    }
    r = requests.post(url, json=payload, headers=headers, timeout=10)
    try:
        data = r.json()
    except Exception:
        r.raise_for_status()
        raise

    if r.status_code >= 400:
        # 토스 표준 에러: {"message":"...", "code":"...", "status":400}
        raise TossError(data.get("message") or "Toss cancel failed", data)
    return data

def pick_last_cancel(toss_payment: dict) -> dict | None:
    """
    토스 응답의 cancels[] 중 마지막 1건 반환 (부분취소 고려 가능).
    """
    cancels = toss_payment.get("cancels") or []
    return cancels[-1] if cancels else None

def shape_cancel_response(payment_obj, toss: dict) -> dict:
    """
    클라이언트 요약 응답(명세) 생성: 카드/간편/계좌이체 vs 가상계좌(입금 전/후)
    """
    base = {
        "payment": {
            "payment_key": payment_obj.payment_key,
            "order_id":    payment_obj.order_id,
            "method":      payment_obj.method,
            "status":      payment_obj.status,
            "amount":      payment_obj.total_amount,
            "currency":    payment_obj.currency,
        }
    }

    last = pick_last_cancel(toss) or {}
    base["cancel"] = {
        "transaction_key": last.get("transactionKey"),
        "receipt_key":     last.get("receiptKey"),
        "cancel_amount":   last.get("cancelAmount"),
        "cancel_reason":   last.get("cancelReason"),
        "canceled_at":     last.get("canceledAt"),
    }

    # 가상계좌(입금 전/후) 분기
    if (payment_obj.method == "가상계좌"):
        # 입금 전 취소는 cancelAmount가 0으로 내려오는 케이스
        # 입금 후 환불이면 refundReceiveAccount 정보가 들어옴
        rra = last.get("refundReceiveAccount") or {}
        if rra:
            base["refund"] = {
                "bank":         rra.get("bank"),
                "accountNumber":rra.get("accountNumber"),
                "holderName":   rra.get("holderName"),
                # 토스가 별도 refundedAt을 주지 않는 경우가 있어 canceledAt 사용
                "refunded_at":  last.get("canceledAt"),
            }
    return base




