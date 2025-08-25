from django.contrib import admin
from .models import Payment, CashReceipt, Cancel, Order

admin.site.register(Order)
admin.site.register(Payment)
admin.site.register(CashReceipt)
admin.site.register(Cancel)
