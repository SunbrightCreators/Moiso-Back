from django.contrib import admin
from .models import Payment, CashReceipt, Cancel

admin.site.register(Payment)
admin.site.register(CashReceipt)
admin.site.register(Cancel)
