from django.core.validators import MinLengthValidator
from django.db import models
from utils.choices import (
    PaymentTypeChoices,
    PaymentMethodChoices,
    PaymentStatusChoices,
    CashReceiptTypeChoices,
    CashReceiptTransactionTypeChoices,
    CashReceiptIssueStatusChoices,
)

class Order(models.Model):
    order_id = models.CharField(
        primary_key=True,
        max_length=64,
        validators=[MinLengthValidator(6)],
        help_text="주문번호(영문/숫자 6~64자)",
    )
    funding = models.ForeignKey(
       "fundings.Funding",
       on_delete=models.PROTECT,
       related_name='order',
    )
    user = models.ForeignKey(
        "accounts.Proposer",
        on_delete=models.CASCADE,
        related_name='order',
    )
    payment = models.OneToOneField(
        "pays.Payment",
        on_delete=models.PROTECT,
        related_name='order',
    )
    item = models.JSONField(
        default=dict,          
        help_text="구매 리워드 스냅샷(JSON)",
    )
    proposer_reward = models.ForeignKey(
        "fundings.ProposerReward",
        on_delete=models.SET_NULL,  # 리워드 삭제돼도 주문은 보존
        related_name='order',
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.order_id


class Payment(models.Model):
    """
    결제(토스 위젯/가상계좌/간편결제 공통)
    - 결제/정산 관련 원본 값은 가급적 JSON 필드에 그대로 저장(포렌식/CS 대응)
    - 취소는 OneToOne Cancel로 연결(정책상 전액취소만 쓰더라도 스키마는 일반형 유지)
    """
    payment_key = models.CharField(
        max_length=200,
        primary_key=True,
    )
    funding = models.ForeignKey(
       "fundings.Funding",
       on_delete=models.PROTECT,
       related_name='payment',
    )
    user = models.ForeignKey(
        "accounts.Proposer",
        on_delete=models.CASCADE,
        related_name='payment',
    )
    version = models.CharField(
        max_length=10,
        default="2022-11-16",
    )
    type = models.CharField(
        max_length=10,
        choices=PaymentTypeChoices.choices,
        default=PaymentTypeChoices.NORMAL,
    )
    order_id = models.CharField(
        max_length=64,
        validators=[MinLengthValidator(6)],
        unique=True,
    )
    order_name = models.CharField(
        max_length=100,
    )
    m_id = models.CharField(
        max_length=14,
    )
    currency = models.CharField(
        max_length=10,
        default="KRW",
    )
    method = models.CharField(
        max_length=20,
        choices=PaymentMethodChoices.choices,
        null=True,
        blank=True,
    )
    total_amount = models.PositiveIntegerField(
        editable=False,
    )
    balance_amount = models.PositiveIntegerField()
    status = models.CharField(
        max_length=32,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.READY,
    )
    requested_at = models.DateTimeField()
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # 옵션/정산 관련
    use_escrow = models.BooleanField()
    last_transaction_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
    )
    supplied_amount = models.PositiveIntegerField()
    vat = models.PositiveIntegerField()
    culture_expense = models.BooleanField()
    tax_free_amount = models.PositiveIntegerField()
    tax_exemption_amount = models.PositiveIntegerField()
    is_partial_cancelable = models.BooleanField()

    # 수단별 세부 정보(토스 원문 JSON 그대로 적재)
    card = models.JSONField(
        null=True,
        blank=True,
        default=dict,
    )
    virtual_account = models.JSONField(
        null=True,
        blank=True,
        default=dict,
    )
    secret = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    mobile_phone = models.JSONField(
        null=True,
        blank=True,
        default=dict,
    )
    gift_certificate = models.JSONField(
        null=True,
        blank=True,
        default=dict,
    )
    transfer = models.JSONField(
        null=True,
        blank=True,
        default=dict,
    )

    # 부가 데이터(원문/추적)
    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="결제 요청 시 추가할 수 있는 metadata (최대 5개, key 최대 40자, value 최대 500자)",
        default=dict,
    )
    receipt = models.JSONField(
        null=True,
        blank=True,
        default=dict,
    )
    checkout = models.JSONField(
        null=True,
        blank=True,
        default=dict,
    )
    easy_pay = models.JSONField(
        null=True,
        blank=True,
        default=dict,
    )
    country = models.CharField(
        max_length=2,
        null=True,
        blank=True,
    )
    failure = models.JSONField(
        null=True,
        blank=True,
        default=dict,
    )
    discount = models.JSONField(
        null=True,
        blank=True,
        default=dict,
    )

    # 리포팅 편의 필드(선택)
    items_amount = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    discount_amount = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    donation_amount = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['funding', 'user'],
                name='unique_funding_user',
            )
        ]

    def __str__(self):
        return f"{self.order_id} / {self.status}"

    @property
    def cash_receipt(self):
        """
        최신 현금영수증 1건을 API 응답 형태로 반환
        """
        cr = self.cash_receipts.order_by('-requested_at').first()
        if not cr:
            return None
        return {
            "type": cr.type,
            "receiptKey": cr.receipt_key,
            "issueNumber": cr.issue_number,
            "receiptUrl": cr.receipt_url,
            "amount": cr.amount,
            "taxFreeAmount": cr.tax_free_amount,
        }

class CashReceipt(models.Model):
    """
    현금영수증 이력 (발급/취소 모두 커버)
    """
    receipt_key = models.CharField(
        max_length=200,
        primary_key=True,
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='cash_receipts',
    )
    type = models.CharField(
        max_length=4,
        choices=CashReceiptTypeChoices.choices,
    )
    issue_number = models.CharField(
        max_length=9,
    )
    receipt_url = models.URLField()
    business_number = models.CharField(
        max_length=10,
    )
    transaction_type = models.CharField(
        max_length=7,
        choices=CashReceiptTransactionTypeChoices.choices,
    )
    amount = models.PositiveIntegerField()
    tax_free_amount = models.PositiveIntegerField()
    issue_status = models.CharField(
        max_length=11,
        choices=CashReceiptIssueStatusChoices.choices,
    )
    customer_identity_number = models.CharField(
        max_length=30,
    )
    requested_at = models.DateTimeField()

    def __str__(self):
        return f"CashReceipt {self.receipt_key} / {self.issue_status}"

class Cancel(models.Model):
    """
    결제 취소(전액/부분 지원 형태 스키마) — 서비스 정책상 전액만 사용하더라도 구조는 유지
    """
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        related_name='cancel',
    )
    cancel_amount = models.PositiveIntegerField()
    cancel_reason = models.CharField(
        max_length=200,
    )
    tax_free_amount = models.PositiveIntegerField()
    tax_exemption_amount = models.PositiveIntegerField()
    refundable_amount = models.PositiveIntegerField()
    card_discount_amount = models.PositiveIntegerField()
    transfer_discount_amount = models.PositiveIntegerField()
    easy_pay_discount_amount = models.PositiveIntegerField()
    canceled_at = models.DateTimeField()
    transaction_key = models.CharField(
        max_length=64,
    )
    receipt_key = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )
    cancel_status = models.TextField()
    cancel_request_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"Cancel {self.payment.order_id} ({self.cancel_amount})"
