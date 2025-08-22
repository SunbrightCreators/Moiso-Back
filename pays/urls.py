from django.urls import path
from .views import *

app_name = 'pays'

urlpatterns = [
  path("pays", PaysRoot.as_view(), name="pays-create-draft"),
  path("pays/confirm", PaysConfirm.as_view(), name="pays-confirm"),
  path("pays/<str:payment_key>/cancel", PaysCancel.as_view(), name="pays-cancel"),
]