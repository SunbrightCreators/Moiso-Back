from django.db import models

# Create your models here.

class Payment(models.Model):
    payment_key = models.CharField(max_length=100, unique=True)
    order_id = models.CharField(max_length=100)
    amount = models.IntegerField()
    method = models.CharField(max_length=50)
    card_company = models.CharField(max_length=50, null=True, blank=True)
    card_number = models.CharField(max_length=100, null=True, blank=True)
    approved_at = models.DateTimeField()
    currency = models.CharField(max_length=10, default="KRW")

    def __str__(self):
        return f"[{self.method}] {self.order_id} - {self.amount}{self.currency}"
    

class Cancel(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='cancels')
    cancel_amount = models.IntegerField()
    canceled_at = models.DateTimeField
    cancel_status = models.CharField(max_length=50)
    transaction_key = models.CharField(max_length=64)
    receipt_key = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"Cancel {self.cancel_amount}원 - {self.cancel_status}"
