from django.urls import path
from .views import *

app_name = 'recommendations'

urlpatterns = [
    path('proposal/overall', ProposalOverall.as_view()),
    path('proposal/scrap-similarity', ProposalScrapSimilarity.as_view()),
    path('proposal/funding-success-similarity', ProposalFundingSuccessSimilarity.as_view()),
]
