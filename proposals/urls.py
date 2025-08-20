from django.urls import path
from .views import *

app_name = 'proposals'

urlpatterns = [
    path('proposer/like', ProposerLike.as_view()),
    path('<str:profile>/scrap', ProfileScrap.as_view()),
]
