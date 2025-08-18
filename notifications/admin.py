from django.contrib import admin
from .models import ProposerNotification, FounderNotification

admin.site.register(ProposerNotification)
admin.site.register(FounderNotification)
