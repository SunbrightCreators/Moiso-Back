from typing import Literal
import requests
from django.conf import settings
from rest_framework.exceptions import NotFound
from .types import PositionType, AddressType, NaverGeocodingAPIType, NaverReverseGeocodingAPIType

class GeocodingService:
    def get_geocoding(
            self,
            query:str,
            coordinate:str|None=None,
            filter:int|None=None,
            language:Literal['kor','eng']|None=None,
            page:int|None=None,
            count:int|None=None
        ) -> NaverGeocodingAPIType.ResponseType:
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
            response (NaverGeocodingAPIType.ResponseType)
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

    def get_address_to_position(self, query_address:str) -> PositionType:
        '''
        주소를 좌표(위도,경도)로 변환합니다.
        Args:
            query_address (str): 주소
        Returns:
            position (PositionType): 좌표
        '''
        response = self.get_geocoding(
            query=query_address,
            count=1,
        )

        if not response.get('addresses'):
            raise NotFound('좌표를 찾을 수 없어요.')

        first_address = response['addresses'][0]

        return  {
            'latitude': float(first_address['x']),
            'longitude': float(first_address['y'])
        }

    def get_address_to_legal(self, query_address:str) -> list[dict]:
        '''
        일부 주소로 법정동 주소와 좌표를 검색합니다.
        Args:
            query_address (str): 주소
        Returns:
            result (list[dict]): 딕셔너리(인덱스 번호, 법정동 주소, 좌표)의 배열
        '''
        response = self.get_geocoding(
            query=query_address,
        )

        if not response.get('addresses'):
            raise NotFound('검색 결과가 없어요.')

        result = list()

        for index, address in enumerate(response['addresses'], start=1):
            sido = next((address_element for address_element in address['addressElements'] if address_element['types'][0] == 'SIDO'), {}).get('longName')
            sigungu = next((address_element for address_element in address['addressElements'] if address_element['types'][0] == 'SIGUGUN'), {}).get('longName')
            eupmyundong = next((address_element for address_element in address['addressElements'] if address_element['types'][0] == 'DONGMYUN'), {}).get('longName')
 
            result.append({
                'id': index,
                'address': {
                    'sido': sido,
                    'sigungu': sigungu,
                    'eupmyundong': eupmyundong,
                },
                'position': {
                    'latitude': float(address.get('x')),
                    'longitude': float(address.get('y')),
                }
            })

        if not result:
            raise NotFound('검색 결과가 없어요.')

        return result

    def get_address_to_full(self, query_address:str, filter_address:str|None=None, filter_type:Literal['road']|None=None) -> list[dict]:
        '''
        일부 주소로 전체 주소와 좌표를 검색합니다.
        Args:
            query_address (str): 검색어
            filter_address (str|None): 법정동 주소. 해당 법정동 내의 주소만 포함합니다.
            filter_type (Literal['road']|None):
                - `None`: 필터하지 않음 (기본값)
                - `'road'`: 도로명 주소가 있는 주소만 포함
        Returns:
            result (list[dict]): 딕셔너리(인덱스 번호, 전체 주소, 좌표)의 배열
        '''
        response = self.get_geocoding(
            query=query_address,
        )

        if not response.get('addresses'):
            raise NotFound('검색 결과가 없어요.')

        result = list()

        for index, address in enumerate(response['addresses'], start=1):
            road_name = next((address_element for address_element in address['addressElements'] if address_element['types'][0] == 'ROAD_NAME'), {}).get('longName')

            if filter_type == 'road':
                if not road_name:
                    continue

            sido = next((address_element for address_element in address['addressElements'] if address_element['types'][0] == 'SIDO'), {}).get('longName')
            sigungu = next((address_element for address_element in address['addressElements'] if address_element['types'][0] == 'SIGUGUN'), {}).get('longName')
            eupmyundong = next((address_element for address_element in address['addressElements'] if address_element['types'][0] == 'DONGMYUN'), {}).get('longName')
 
            if filter_address:
                if not filter_address == ' '.join([sido, sigungu, eupmyundong]):
                    continue

            ri = next((address_element for address_element in address['addressElements'] if address_element['types'][0] == 'RI'), {}).get('longName')
            land_number = next((address_element for address_element in address['addressElements'] if address_element['types'][0] == 'LAND_NUMBER'), {}).get('longName')
            building_number = next((address_element for address_element in address['addressElements'] if address_element['types'][0] == 'BUILDING_NUMBER'), {}).get('longName')
            building_name = next((address_element for address_element in address['addressElements'] if address_element['types'][0] == 'BUILDING_NAME'), {}).get('longName')

            jibun_detail = ' '.join(filter(None, [ri, land_number]))
            road_detail = ' '.join(filter(None, [road_name, building_number, building_name]))

            result.append({
                'id': index,
                'address': {
                    'sido': sido,
                    'sigungu': sigungu,
                    'eupmyundong': eupmyundong,
                    'jibun_detail': jibun_detail,
                    'road_detail': road_detail,
                },
                'position': {
                    'latitude': float(address.get('x')),
                    'longitude': float(address.get('y')),
                }
            })

        if not result:
            raise NotFound('검색 결과가 없어요.')

        return result

class ReverseGeocodingService:
    def get_reverse_geocoding(
            self,
            coords:str,
            sourcecrs:Literal['EPSG:4326','EPSG:3857','NHN:2048']|None=None,
            targetcrs:Literal['EPSG:4326','EPSG:3857','NHN:2048']|None=None,
            orders:list[Literal['legalcode','admcode','addr','roadaddr']]|None=None
        ) -> NaverReverseGeocodingAPIType.ResponseType:
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
            response (NaverReverseGeocodingAPIType.ResponseType)
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

    def get_position_to_legal(self, query_position:PositionType) -> AddressType.LegalType:
        '''
        좌표(위도,경도)를 법정동 주소로 변환합니다.
        Args:
            query_position (PositionType): 좌표
        Returns:
            address (AddressType.LegalType): 법정동 주소
        '''
        response = self.get_reverse_geocoding(
            coords=f"{query_position['latitude']},{query_position['longitude']}",
            orders=['legalcode']
        )

        if not response.get('results'):
            raise NotFound('주소를 찾을 수 없어요.')

        legalcode = response['results'][0]
        sido = legalcode.get('region', {}).get('area1', {}).get('name') or None
        sigungu = legalcode.get('region', {}).get('area2', {}).get('name') or None
        eupmyundong = legalcode.get('region', {}).get('area3', {}).get('name') or None

        return {
            'sido': sido,
            'sigungu': sigungu,
            'eupmyundong': eupmyundong,
        }

    def get_position_to_full(self, query_position:PositionType, filter_address:str|None=None) -> AddressType.FullType:
        '''
        좌표(위도,경도)를 전체 주소로 변환합니다.
        Args:
            query_position (PositionType): 좌표
            filter_address (str|None): 법정동 주소. 해당 법정동 내의 주소만 포함합니다.
        Returns:
            address (AddressType.FullType): 전체 주소
        '''
        response = self.get_reverse_geocoding(
            coords=f"{query_position['latitude']},{query_position['longitude']}",
            orders=['legalcode','addr','roadaddr']
        )

        if not response.get('results'):
            raise NotFound('주소를 찾을 수 없어요.')
        
        legalcode = next((item for item in response['results'] if item['name'] == 'legalcode'), None)
        sido = legalcode.get('region', {}).get('area1', {}).get('name') or None
        sigungu = legalcode.get('region', {}).get('area2', {}).get('name') or None
        eupmyundong = legalcode.get('region', {}).get('area3', {}).get('name') or None

        if filter_address:
            if not filter_address == ' '.join([sido, sigungu, eupmyundong]):
                raise NotFound('핀을 우리 동네로 옮겨 주세요.')

        addr = next((item for item in response['results'] if item['name'] == 'addr'), None)
        if addr:
            jibun_detail = ' '.join(
                filter(None, [
                    addr.get('region', {}).get('area4', {}).get('name'),
                    addr.get('land', {}).get('number1')
                ])
            )
            if addr.get('land', {}).get('number2'):
                jibun_detail += ('-' + addr['land']['number2'])
        else:
            jibun_detail = None

        roadaddr = next((item for item in response['results'] if item['name'] == 'roadaddr'), None)
        if roadaddr:
            road_detail = ' '.join(
                filter(None, [
                    roadaddr.get('land', {}).get('name'),
                    roadaddr.get('land', {}).get('number1'),
                ])
            )
        else:
            road_detail = None

        return {
            'sido': sido,
            'sigungu': sigungu,
            'eupmyundong': eupmyundong,
            'jibun_detail': jibun_detail,
            'road_detail': road_detail,
        }
