from django.urls import path
from .views import *

app_name = 'maps'

urlpatterns = [
    path('geocoding/position', GeocodingPosition.as_view()),
    path('geocoding/legal', GeocodingLegal.as_view()),
    path('reverse-geocoding/legal', ReverseGeocodingLegal.as_view()),
    path('reverse-geocoding/full', ReverseGeocodingFull.as_view()),
]