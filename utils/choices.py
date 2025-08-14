from django.db.models import TextChoices, IntegerChoices

class ExampleChoices(IntegerChoices):
    '''
    예시 코드입니다.
    '''
    ONE = 1, '일'
    TWO = 2, '이'
    THREE = 3, '삼'

class SexChoices(TextChoices):
    WOMAN = 'WOMAN', '여성'
    MAN = 'MAN', '남성'

class IndustryChoices(TextChoices):
    FOOD_DINING          = 'FOOD_DINING',          '외식/음식점'
    CAFE_DESSERT         = 'CAFE_DESSERT',         '카페/디저트'
    PUB_BAR              = 'PUB_BAR',              '주점'
    CONVENIENCE_RETAIL   = 'CONVENIENCE_RETAIL',   '편의점/소매'
    GROCERY_MART         = 'GROCERY_MART',         '마트/식료품'
    BEAUTY_CARE          = 'BEAUTY_CARE',          '뷰티/미용'
    HEALTH_FITNESS       = 'HEALTH_FITNESS',       '건강'
    FASHION_GOODS        = 'FASHION_GOODS',        '패션/잡화'
    HOME_LIVING_INTERIOR = 'HOME_LIVING_INTERIOR', '생활용품/가구/인테리어'
    HOBBY_LEISURE        = 'HOBBY_LEISURE',        '취미/오락/여가'
    CULTURE_BOOKS        = 'CULTURE_BOOKS',        '문화/서적'
    PET                  = 'PET',                  '반려동물'
    LODGING              = 'LODGING',              '숙박'
    EDUCATION_ACADEMY    = 'EDUCATION_ACADEMY',    '교육/학원'
    AUTO_TRANSPORT       = 'AUTO_TRANSPORT',       '자동/운송'
    IT_OFFICE            = 'IT_OFFICE',            'IT/사무'
    FINANCE_LEGAL_TAX    = 'FINANCE_LEGAL_TAX',    '금융/법률/회계'
    MEDICAL_PHARMA       = 'MEDICAL_PHARMA',       '의료/의약'
    PERSONAL_SERVICES    = 'PERSONAL_SERVICES',    '생활 서비스'
    FUNERAL_WEDDING      = 'FUNERAL_WEDDING',      '장례/예식'
    PHOTO_STUDIO         = 'PHOTO_STUDIO',         '사진/스튜디오'
    OTHER_RETAIL         = 'OTHER_RETAIL',         '기타 판매업'
    OTHER_SERVICE        = 'OTHER_SERVICE',        '기타 서비스업'

class RadiusChoices(IntegerChoices):
    M0      =     0,   '0m'
    M250    =   250, '250m'
    M500    =   500, '500m'
    M750    =   750, '750m'
    M1000   = 1_000,'1000m'

class ZoomChoices(IntegerChoices):
    M0     =      0,   '0m'
    M500   =    500, '500m'
    M2000  =  2_000,  '2km'
    M10000 = 10_000, '10km'

class FounderTargetChoices(TextChoices):
    LOCAL = 'LOCAL', '동네주민'
    STRANGER = 'STRANGER', '외부인'

class FundingStatusChoices(TextChoices):
    PENDING = 'PENDING', '심사 중'
    APPROVED = 'APPROVED', '승인됨'
    REJECTED = 'REJECTED', '반려됨'
    IN_PROGRESS = 'IN_PROGRESS', '진행 중'
    SUCCEEDED = 'SUCCEEDED', '성공'
    FAILED = 'FAILED', '실패'

class BankCategoryChoices(TextChoices):
    NATURAL = 'NATURAL', '개인'
    LEGAL = 'LEGAL', '법인'

class RewardCategoryChoices(TextChoices):
    COUPON = 'COUPON', '펀딩 할인쿠폰'
    GIFT = 'GIFT', '펀딩 선물증정'
    LEVEL = 'LEVEL', '레벨'

class RewardAmountChoices(IntegerChoices):
    W5K = 5_000, '5천원'
    W10K = 10_000, '1만원'
    W30K = 30_000, '3만원'
    W50K = 50_000, '5만원'

class PaymentTypeChoices(TextChoices):
    NORMAL = 'NORMAL', '일반 결제'
    BILLING = 'BILLING', '자동결제'
    BRANDPAY = 'BRANDPAY', '브랜드페이'

class PaymentMethodChoices(TextChoices):
    CARD = '카드'
    VIRTUAL_ACCOUNT = '가상계좌'
    EASY_PAY = '간편결제'
    MOBILE_PHONE = '휴대폰'
    TRANSFER = '계좌이체'
    GIFT_CERTIFICATE = '문화상품권'
    CULTURE_GIFT_CERT = '도서문화상품권'
    GAME_GIFT_CERT = '게임문화상품권'

class PaymentStatusChoices(TextChoices):
    READY = 'READY', '요청 생성'
    IN_PROGRESS = 'IN_PROGRESS', '승인 중'
    WAITING_FOR_DEPOSIT = 'WAITING_FOR_DEPOSIT', '입금 대기'
    DONE = 'DONE', '승인 완료'
    CANCELED = 'CANCELED',  '전체 취소'
    PARTIAL_CANCELED = 'PARTIAL_CANCELED',  '부분 취소'
    ABORTED = 'ABORTED', '승인 실패/중단'
    EXPIRED = 'EXPIRED', '만료'

class CashReceiptTypeChoices(TextChoices):
    INCOME_DEDUCTION = '소득공제'
    EXPENSE_PROOF  = '지출증빙'

class CashReceiptTransactionTypeChoices(TextChoices):
    CONFIRM = 'CONFIRM', '발급'
    CANCEL = 'CANCEL', '취소'

class CashReceiptIssueStatusChoices(TextChoices):
    IN_PROGRESS = 'IN_PROGRESS', '발급 진행 중'
    COMPLETED = 'COMPLETED', '발급 완료'
    FAILED = 'FAILED', '발급 실패'

class NotificationCategoryChoices(TextChoices):
    FUNDING = 'FUNDING', '펀딩'
    REWARD = 'REWARD', '리워드'
