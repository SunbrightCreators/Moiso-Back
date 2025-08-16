from django.http import HttpRequest
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .services import NaverMapService

class GeocodingRoot(APIView):
    def get(self, request:HttpRequest, format=None):
        address = request.query_params.get('address')

        service = NaverMapService()
        position = service.get_address_to_position(address)

        return Response(
            position,
            status=status.HTTP_200_OK,
        )

class ReverseGeocodingFull(APIView):
    def get(self, request:HttpRequest, format=None):
        latitude = request.query_params.get('latitude')
        longitude = request.query_params.get('longitude')

        service = NaverMapService()
        address = service.get_position_to_full({
            'latitude': latitude,
            'longitude': longitude,
        })

        return Response(
            address,
            status=status.HTTP_200_OK,
        )

class ReverseGeocodingLegal(APIView):
    def get(self, request:HttpRequest, format=None):
        latitude = request.query_params.get('latitude')
        longitude = request.query_params.get('longitude')

        service = NaverMapService()
        address = service.get_position_to_legal({
            'latitude': latitude,
            'longitude': longitude,
        })

        return Response(
            address,
            status=status.HTTP_200_OK,
        )
