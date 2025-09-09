from django.http import HttpRequest
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from utils.decorators.view import require_query_params
from .services import GeocodingService, ReverseGeocodingService

class GeocodingPosition(APIView):
    @method_decorator(require_query_params('query'))
    def get(self, request:HttpRequest, format=None):
        query = request.query_params.get('query')

        service = GeocodingService()
        position = service.get_address_to_position(query)

        return Response(
            position,
            status=status.HTTP_200_OK,
        )

class GeocodingLegal(APIView):
    @method_decorator(require_query_params('query'))
    def get(self, request:HttpRequest, format=None):
        query = request.query_params.get('query')

        service = GeocodingService()
        legal = service.get_address_to_legal(query)

        return Response(
            legal,
            status=status.HTTP_200_OK,
        )

class GeocodingFull(APIView):
    @method_decorator(require_query_params('query'))
    def get(self, request:HttpRequest, format=None):
        query = request.query_params.get('query')
        filter = request.query_params.get('filter')

        service = GeocodingService()
        full = service.get_address_to_full(query, filter, 'road')

        return Response(
            full,
            status=status.HTTP_200_OK,
        )

class ReverseGeocodingLegal(APIView):
    @method_decorator(require_query_params('latitude','longitude'))
    def get(self, request:HttpRequest, format=None):
        latitude = request.query_params.get('latitude')
        longitude = request.query_params.get('longitude')

        service = ReverseGeocodingService()
        legal = service.get_position_to_legal(
            {
                'latitude': latitude,
                'longitude': longitude,
            }
        )

        return Response(
            legal,
            status=status.HTTP_200_OK,
        )

class ReverseGeocodingFull(APIView):
    @method_decorator(require_query_params('latitude','longitude'))
    def get(self, request:HttpRequest, format=None):
        latitude = request.query_params.get('latitude')
        longitude = request.query_params.get('longitude')
        filter = request.query_params.get('filter')

        service = ReverseGeocodingService()
        full = service.get_position_to_full(
            {
                'latitude': latitude,
                'longitude': longitude,
            },
            filter,
        )

        return Response(
            full,
            status=status.HTTP_200_OK,
        )
