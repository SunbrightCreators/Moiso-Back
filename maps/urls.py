from django.urls import path
from .views import *

app_name = 'maps'

urlpatterns = [
    path('geocoding', GeocodingRoot.as_view()),
    path('reverse-geocoding/full', ReverseGeocodingFull.as_view()),
    path('reverse-geocoding/legalcode', ReverseGeocodingAdmcode.as_view()),
]