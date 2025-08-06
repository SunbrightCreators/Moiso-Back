from django.urls import path
from .views import ConfirmPaymentAPIViewRoot, CancelPaymentAPIViewRoot, RetrievePaymentAPIViewRoot

urlpatterns = [
    path("confirm/", ConfirmPaymentAPIViewRoot.as_view(), name="confirm_payment"),
    path('cancel/', CancelPaymentAPIViewRoot.as_view(), name='cancel-payment'),
    path('retrieve/', RetrievePaymentAPIViewRoot.as_view(), name='retrieve-payment'),
]