from django.urls import path
from .views import (
    AccountsLoginRoot,
    AccountsAccessTokenRoot,
    AccountsRoot,
    AccountsProfileRoot,
)

app_name = 'accounts'

urlpatterns = [
    path("login", AccountsLoginRoot.as_view(), name="accounts-login"),
    path("access-token", AccountsAccessTokenRoot.as_view(), name="accounts-access-token"),
    path("", AccountsRoot.as_view(), name="accounts-root"),
    path("<str:profile>", AccountsProfileRoot.as_view(), name="accounts-profile"),
]
