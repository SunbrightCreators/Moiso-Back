from django.urls import path
from .views import *

app_name = 'accounts'

urlpatterns = [
  path("login", LoginView.as_view(), name="accounts-login"),
  path("access-token", AccessTokenIssueView.as_view(), name="accounts-access-token"),
]
