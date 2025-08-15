from typing import TypedDict, Literal

class PositionType(TypedDict):
    '''
    좌표
    Attributes:
        latitude (int): 위도
        longitude (int): 경도
    '''
    latitude: int
    longitude: int

class MetaType(TypedDict):
    '''
    메타 데이터
    Attributes:
        totalCount (int): 응답 결과 개수
        page (int): 현재 페이지 번호
        count (int): 페이지 내 결과 개수
    '''
    totalCount: int
    page: int
    count: int

class AddressElementType(TypedDict):
    '''
    주소 구성 요소 정보
    Attributes:
        type (list[Literal['SIDO','SIGUGUN','DONGMYUN','RI','ROAD_NAME','BUILDING_NUMBER','BUILDING_NAME','LAND_NUMBER','POSTAL_CODE']]): 주소 구성 요소 타입
            - `SIDO`: 시/도
            - `SIGUGUN`: 시/구/군
            - `DONGMYUN`: 동/면
            - `RI`: 리
            - `ROAD_NAME`: 도로명
            - `BUILDING_NUMBER`: 건물 번호
            - `BUILDING_NAME`: 건물 이름
            - `LAND_NUMBER`: 번지
            - `POSTAL_CODE`: 우편번호
        longName (str): 주소 구성 요소 이름
        shortName (str): 주소 구성 요소 축약 이름
        code (str):
    '''
    type: list[Literal['SIDO','SIGUGUN','DONGMYUN','RI','ROAD_NAME','BUILDING_NUMBER','BUILDING_NAME','LAND_NUMBER','POSTAL_CODE']]
    longName: str
    shortName: str
    code: str

class AddressType(TypedDict):
    '''
    주소 정보
    Attributes:
        roadAddress (str): 도로명 주소
        jibunAddress (str): 지번 주소
        englishAddress (str): 영어 주소
        addressElements (list[AddressElementType]): 주소 구성 요소 정보
        x (str): X 좌표(경도)
        y (str): Y 좌표(위도)
        distance (float): 중심 좌표로부터의 거리(m)
    '''
    roadAddress: str
    jibunAddress: str
    englishAddress: str
    addressElements: list[AddressElementType]
    x: str
    y: str
    distance: float

class GeocodingResponseType(TypedDict):
    '''
    응답 바디
    Attributes:
        status (str): 응답 코드
        meta (MetaType): 메타 데이터
        addresses (list[AddressType]): 주소 정보 목록
        errorMessage (str|Literal['']): 오류 메시지 (500 오류 발생 시에만 표시)
    '''
    status: str
    meta: MetaType
    addresses: list[AddressType]
    errorMessage: str|Literal['']


class StatusType(TypedDict):
    '''
    응답 상태에 대한 정보
    Attributes:
        code (int): 응답 상태 코드
        name (str): 응답 상태 메시지
        message (str): 	응답 상태에 대한 설명
    '''
    code: int
    name: str
    message: str

class CodeType(TypedDict):
    '''
    코드 정보
    Attributes:
        id (str): 코드 ID
        type (Literal['L','A','S']): 코드 타입
            - `L`: 법정동
            - `A`: 행정동
            - `S`: 영역은 다르지만 동일한 이름의 법정동이 존재하는 행정동
        mappingId (str): 법정/행정 코드에 매핑된 네이버 동 코드의 ID
    '''
    id: str
    type: Literal['L','A','S']
    mappingId: str

class CoordsCenterType(TypedDict):
    '''
    행정 구역 중심 좌표
    Attributes:
        crs (str): 좌표계 코드
        x (float): X 좌표 (land.coords.center.crs이 EPSG:4326인 경우, 경도)
        y (float): Y 좌표 (land.coords.center.crs이 EPSG:4326인 경우, 위도)
    '''
    crs: str
    x: float
    y: float

class CoordsType(TypedDict):
    '''
    행정 구역 위치 정보
    Attributes:
        center (CoordsCenterType): 행정 구역 중심 좌표
    '''
    center: CoordsCenterType

class RegionAreaNType(TypedDict):
    '''
    행정 구역 정보
    Attributes:
        name (str): 행정 구역 단위 이름
        coords (CoordsType): 행정 구역 위치 정보
        alias (str|None): 행정 구역 줄임말
    '''
    name: str
    coords: CoordsType
    alias: str|None

class RegionType(TypedDict):
    '''
    주소 정보
    Attributes:
        areaN (RegionAreaNType): 행정 구역 정보 (변환된 주소의 가장 큰 행정 구역 단위부터 순차적으로 표시)
        area0.name (`kr`): 국가 코드 최상위 도메인으로, `kr` 표시
        area1.name (str): 행정안전부에서 공시한 시/도 이름
        area2.name (str): 행정안전부에서 공시한 시/군/구 이름
        area3.name (str): 행정안전부에서 공시한 읍/면/동 이름
        area4.name (str): 행정안전부에서 공시한 리 이름
    '''
    area0: RegionAreaNType
    area1: RegionAreaNType
    area2: RegionAreaNType
    area3: RegionAreaNType
    area4: RegionAreaNType

class LandAdditionNType(TypedDict):
    '''
    추가 정보
    Attributes:
        type (str): 추가 정보 타입
        value (str): 추가 정보 값
    '''
    type: str
    value: str

class LandType(TypedDict):
    '''
    상세 주소 정보
    Attributes:
        type (Literal['1','2']|Literal['']): 지적 타입 (name이 addr인 경우에만 상세 값 표시)
            - `1`: 일반 토지
            - `2`: 산
        name (str|None): 도로 이름 (name이 roadaddr인 경우에만 상세 값 표시)
        number1 (str): 상세 번호
            - name이 `addr`인 경우 토지 본번호
            - name이 `roadaddr`인 경우 상세 주소
        number2 (str|Literal['']): 토지 부번호 (name이 addr인 경우에만 상세 값 표시)
        coords (CoordsType): 상세 주소 위치 정보
        addition0 (LandAdditionNType): 건물 정보 (name이 roadaddr인 경우에만 상세 값 표시)
            - type: `building`
            - value: 건물 이름
        addition1 (LandAdditionNType): 우편 번호 정보 (name이 roadaddr인 경우에만 상세 값 표시)
            - type: `zipcode`
            - value: 우편번호
        addition2 (LandAdditionNType): 도로 코드 정보 (name이 roadaddr인 경우에만 상세 값 표시)
            - type: `roadGroupCode`
            - value: 도로 코드(12자리)
    '''
    type: Literal['1','2']|Literal['']
    name: str|None
    number1: str
    number2: str|Literal['']
    coords: CoordsType
    addition0: LandAdditionNType
    addition1: LandAdditionNType
    addition2: LandAdditionNType
    addition3: LandAdditionNType
    addition4: LandAdditionNType

class ResultType(TypedDict):
    '''
    응답 결과
    Attributes:
        name (str): 변환 타입
        code (CodeType): 코드 정보
        region (RegionType): 주소 정보
        land (LandType): 상세 주소 정보
    '''
    name: str
    code: CodeType
    region: RegionType
    land: LandType

class ReverseGeocodingResponseType(TypedDict):
    '''
    응답 바디
    Attributes:
        status (StatusType): 응답 상태에 대한 정보
        results (list[ResultType]): 응답 결과
    '''
    status: StatusType
    results: list[ResultType]
