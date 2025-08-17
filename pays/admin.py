from django.contrib import admin
from .models import *

admin.site.register(Payment)
admin.site.register(Cancel)
admin.site.register(CashReceipt)

