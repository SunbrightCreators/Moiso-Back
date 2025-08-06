from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path("signup/", views.SignUpViewRoot.as_view()),
    path("login/", views.LoginViewRoot.as_view()),
]
