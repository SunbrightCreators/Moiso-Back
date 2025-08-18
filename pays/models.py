from django.conf import settings
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


class Payment(models.Model):
    """
    결제(토스 위젯/가상계좌/간편결제 공통)
    - 결제/정산 관련 원본 값은 가급적 JSON 필드에 그대로 저장(포렌식/CS 대응)
    - 취소는 OneToOne Cancel로 연결(정책상 전액취소만 쓰더라도 스키마는 일반형 유지)
    """

    payment_key = models.CharField(
        max_length=200,
        unique=True,
    )
    # funding = models.ForeignKey(
    #     'fundings.Funding',
    #     on_delete=models.PROTECT,
    #     related_name='payments',
    # )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
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
    )
    total_amount = models.PositiveIntegerField()
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
    use_escrow = models.BooleanField(
        default=False,
    )
    last_transaction_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
    )
    supplied_amount = models.PositiveIntegerField(
        default=0,
    )
    vat = models.PositiveIntegerField(
        default=0,
    )
    culture_expense = models.BooleanField(
        default=False,
    )
    tax_free_amount = models.PositiveIntegerField(
        default=0,
    )
    tax_exemption_amount = models.PositiveIntegerField(
        default=0,
    )
    is_partial_cancelable = models.BooleanField(
        default=False,
    )

    # 수단별 세부 정보(토스 원문 JSON 그대로 적재)
    card = models.JSONField(
        null=True,
        blank=True,
    )
    virtual_account = models.JSONField(
        null=True,
        blank=True,
    )
    secret = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    mobile_phone = models.JSONField(
        null=True,
        blank=True,
    )
    gift_certificate = models.JSONField(
        null=True,
        blank=True,
    )
    transfer = models.JSONField(
        null=True,
        blank=True,
    )

    # 부가 데이터(원문/추적)
    metadata = models.JSONField(
        null=True,
        blank=True,
    )
    receipt = models.JSONField(
        null=True,
        blank=True,
    )
    checkout = models.JSONField(
        null=True,
        blank=True,
    )
    easy_pay = models.JSONField(
        null=True,
        blank=True,
    )
    country = models.CharField(
        max_length=2,
        null=True,
        blank=True,
    )
    failure = models.JSONField(
        null=True,
        blank=True,
    )
    discount = models.JSONField(
        null=True,
        blank=True,
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
        return f"{self.order_id} / {self.get_status_display()}"

    @property
    def cash_receipt(self):
        """
        최신 현금영수증 1건을 API 응답 형태로 반환
        """
        cr = self.cash_receipts.order_by('-requested_at').first()
        if not cr:
            return None

        return {
            "type": cr.get_type_display(),
            "receiptKey": cr.receipt_key,
            "issueNumber": cr.issue_number,
            "receiptUrl": cr.receipt_url,
            "amount": cr.amount,
            "taxFreeAmount": cr.tax_free_amount,
        }


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
    cancel_reason = models.TextField(
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
        return f"CashReceipt {self.receipt_key} / {self.get_issue_status_display()}"

