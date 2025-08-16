from typing import Literal
import requests
from django.conf import settings
from rest_framework.exceptions import NotFound
from .types import PositionType, AddressType, NaverGeocodingAPI, NaverReverseGeocodingAPI

class NaverMapService:
    def get_geocoding(
            self,
            query:str,
            coordinate:str|None=None,
            filter:int|None=None,
            language:Literal['kor','eng']|None=None,
            page:int|None=None,
            count:int|None=None
        ) -> NaverGeocodingAPI.ResponseType:
        '''
        입력한 주소를 검색하여 좌표를 포함한 상세 정보 제공
        Args:
            query (str): 검색할 주소
            coordinate (str|None): 검색 중심 좌표(경도,위도), 입력한 좌표와 근접한 순으로 검색 결과 표시
            filter (int|None): 검색 결과 필터 (예: `HCODE@4113554500;4113555000`)
                - `HCODE`: 행정동 코드
                - `BCODE`: 법정동 코드
            language (Literal['kor','eng']|None): 응답 결과 언어
                - `'kor'`: 한국어 (기본값)
                - `'eng'`: 영어
            page (int|None): 페이지 번호
                - `1`: (기본값)
            count (int|None): 결과 목록 크기 `1` ~ `100` (기본값: `10`)
        Returns:
            response (NaverGeocodingAPI.ResponseType)
        '''
        response = requests.get(
            url='https://maps.apigw.ntruss.com/map-geocode/v2/geocode',
            params={
                'query': query,
                'coordinate': coordinate,
                'filter': filter,
                'language': language,
                'page': page,
                'count': count,
            },
            headers={
                'x-ncp-apigw-api-key-id': settings.NCLOUD_CLIENT_ID,
                'x-ncp-apigw-api-key': settings.NCLOUD_CLIENT_SECRET,
                'Accept': 'application/json'
            }
        )
        return response.json()

    def get_reverse_geocoding(
            self,
            coords:str,
            sourcecrs:Literal['EPSG:4326','EPSG:3857','NHN:2048']|None=None,
            targetcrs:Literal['EPSG:4326','EPSG:3857','NHN:2048']|None=None,
            orders:list[Literal['legalcode','admcode','addr','roadaddr']]|None=None
        ) -> NaverReverseGeocodingAPI.ResponseType:
        '''
        좌표를 검색하여 법정동, 행정동, 지번 주소, 도로명 주소 등 주소 정보 제공
        Args:
            coords (str): 좌표(X 좌표,Y 좌표) (예: `coords=128.12345,37.98776`)
            sourcecrs (Literal['EPSG:4326','EPSG:3857','NHN:2048']|None): 입력 좌표계 코드
                - `'EPSG:4326'`: WGS84 경위도 (기본값)
                - `'EPSG:3857'`: 구글 맵
                - `'NHN:2048'`: UTM-K
            targetcrs (Literal['EPSG:4326','EPSG:3857','NHN:2048']|None): 출력 좌표계 코드
                - `'EPSG:4326'`: WGS84 경위도 (기본값)
                - `'EPSG:3857'`: 구글 맵
                - `'NHN:2048'`: UTM-K
            orders (list[Literal['legalcode','admcode','addr','roadaddr']]|None): 변환 타입. `,`로 구분하여 여러 옵션 값을 입력할 수 있으며 입력순으로 결과 표시 (예: `orders=legalcode,addr`)
                - `'legalcode'`: 법정동으로 변환 (기본값)
                - `'admcode'`: 행정동으로 변환 (기본값)
                - `'addr'`: 지번 주소로 변환
                - `'roadaddr'`: 도로명 주소로 변환
        Returns:
            response (NaverReverseGeocodingAPI.ResponseType)
        '''
        response = requests.get(
            url='https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc',
            params={
                'coords': coords,
                'sourcecrs': sourcecrs,
                'targetcrs': targetcrs,
                'orders': ','.join(orders),
                'output': 'json'
            },
            headers={
                'x-ncp-apigw-api-key-id': settings.NCLOUD_CLIENT_ID,
                'x-ncp-apigw-api-key': settings.NCLOUD_CLIENT_SECRET,
            }
        )
        return response.json()

    def get_address_to_position(self, address:str) -> PositionType:
        '''
        주소를 좌표(위도,경도)로 변환합니다.
        Args:
            address (str): 주소
        Returns:
            position (PositionType):
                - latitude (int): 위도
                - longitude (int): 경도
        '''
        response = self.get_geocoding(
            query=address,
            count=1,
        )

        if not response.get('addresses'):
            raise NotFound('좌표를 찾을 수 없어요.')

        first_address = response['addresses'][0]
        x = float(first_address['x'])
        y = float(first_address['y'])

        return  {
            'latitude': x,
            'longitude': y
        }

    def get_position_to_address(self, position:PositionType) -> AddressType:
        '''
        좌표(위도,경도)를 주소로 변환합니다.
        Args:
            position (PositionType):
                - latitude (int): 위도
                - longitude (int): 경도
        Returns:
            address (AddressType):
                - road (str): 도로명 주소
                - jibun (str): 지번 주소
        '''
        response = self.get_reverse_geocoding(
            coords=f'{position['latitude']},{position['longitude']}',
            orders=['roadaddr','addr']
        )

        if not response.get('results'):
            raise NotFound('주소를 찾을 수 없어요.')

        roadaddr = next((item for item in response['results'] if item['name'] == 'roadaddr'), None)
        if roadaddr:
            road = ' '.join(
                filter(None, [
                    roadaddr.get('region').get('area1').get('name'),
                    roadaddr.get('region').get('area2').get('name'),
                    roadaddr.get('region').get('area3').get('name'),
                    roadaddr.get('region').get('area4').get('name'),
                    roadaddr.get('land').get('name'),
                    roadaddr.get('land').get('number1'),
                ])
            )
        else:
            road = None

        addr = next((item for item in response['results'] if item['name'] == 'addr'), None)
        if addr:
            jibun = ' '.join(
                filter(None, [
                    addr.get('region').get('area1').get('name'),
                    addr.get('region').get('area2').get('name'),
                    addr.get('region').get('area3').get('name'),
                    addr.get('region').get('area4').get('name'),
                    addr.get('land').get('number1')
                ])
            )
            if addr.get('land').get('number2'):
                jibun += ('-' + addr['land']['number2'])
        else:
            jibun = None

        return {
            'road': road,
            'jibun': jibun,
        }
    
    def get_position_to_legalcode(self, position:PositionType) -> str:
        '''
        좌표(위도,경도)를 법정동으로 변환합니다.
        Args:
            position (PositionType):
                - latitude (int): 위도
                - longitude (int): 경도
        Returns:
            address (str): 법정동 주소
        '''
        response = self.get_reverse_geocoding(
            coords=f'{position['latitude']},{position['longitude']}',
            orders=['legalcode']
        )

        if not response.get('results'):
            raise NotFound('주소를 찾을 수 없어요.')

        legalcode = response['results'][0]
        address = ' '.join(
            filter(None, [
                legalcode.get('region').get('area1').get('name'),
                legalcode.get('region').get('area2').get('name'),
                legalcode.get('region').get('area3').get('name'),
            ])
        )

        return {
            'legalcode': address,
        }
