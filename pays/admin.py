from django.contrib import admin
from .models import Payment, CashReceipt, Cancel

admin.site.register(Payment)
admin.site.register(Cancel)
admin.site.register(CashReceipt)

