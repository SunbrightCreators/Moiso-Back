from django.db.models import TextChoices, IntegerChoices

class ExampleChoices(IntegerChoices):
    '''
    예시 코드입니다.
    '''
    ONE = 1, '일'
    TWO = 2, '이'
    THREE = 3, '삼'

class IndustryChoices(TextChoices):          # Founder, Proposer, Funding, Proposal 모델에 사용
    FOOD_DINING          = "food_dining",          "외식/음식점"          
    CAFE_DESSERT         = "cafe_dessert",         "카페/디저트"          
    PUB_BAR              = "pub_bar",              "주점"               
    CONVENIENCE_RETAIL   = "convenience_retail",   "편의점/소매"          
    GROCERY_MART         = "grocery_mart",         "마트/식료품"         
    BEAUTY_CARE          = "beauty_care",          "뷰티/미용"             
    HEALTH_FITNESS       = "health_fitness",       "건강"               
    FASHION_GOODS        = "fashion_goods",        "패션/잡화"              
    HOME_LIVING_INTERIOR = "home_living_interior", "생활용품/가구/인테리어"  
    HOBBY_LEISURE        = "hobby_leisure",        "취미/오락/여가"         
    CULTURE_BOOKS        = "culture_books",        "문화/서적"           
    PET                  = "pet",                  "반려동물"        
    LODGING              = "lodging",              "숙박"          
    EDUCATION_ACADEMY    = "education_academy",    "교육/학원"            
    AUTO_TRANSPORT       = "auto_transport",       "자동/운송"            
    IT_OFFICE            = "it_office",            "IT/사무"             
    FINANCE_LEGAL_TAX    = "finance_legal_tax",    "금융/법률/회계"         
    MEDICAL_PHARMA       = "medical_pharma",       "의료/의약"           
    PERSONAL_SERVICES    = "personal_services",    "생활 서비스"       
    FUNERAL_WEDDING      = "funeral_wedding",      "장례/예식"             
    PHOTO_STUDIO         = "photo_studio",         "사진/스튜디오"       
    OTHER_RETAIL         = "other_retail",         "기타 판매업"
    OTHER_SERVICE        = "other_service",        "기타 서비스업"

class FounderTargetChoices(TextChoices):
    LOCAL = "local", "동네주민"
    OUTSIDER = "outsider", "외부인"

class FundingStatusChoices(TextChoices):
    REVIEW = "REVIEW", "심사중"
    APPROVED = "APPROVED", "승인됨"
    REJECTED = "REJECTED", "반려됨"
    ACTIVE = "ACTIVE", "진행중"
    CLOSED = "CLOSED", "종료"


class RewardCategoryChoices(TextChoices):
    COUPON = "coupon", "펀딩 할인쿠폰"
    GIFT = "gift", "펀딩 선물증정"
    LEVEL = "level", "레벨"

class RewardAmountChoices(IntegerChoices):
    W5K = 5_000, "5천원"
    W10K = 10_000, "1만원"
    W30K = 30_000, "3만원"
    W50K = 50_000, "5만원"

class PaymentTypeChoices(TextChoices):
    NORMAL = "NORMAL", "일반 결제"
    BILLING = "BILLING", "자동결제"
    BRANDPAY = "BRANDPAY", "브랜드페이"

class PaymentMethodChoices(TextChoices):
    CARD = "CARD", "카드"
    VIRTUAL_ACCOUNT = "VIRTUAL_ACCOUNT", "가상계좌"
    EASY_PAY = "EASY_PAY", "간편결제"
    MOBILE_PHONE = "MOBILE_PHONE", "휴대폰"
    TRANSFER = "TRANSFER", "계좌이체"
    GIFT_CERTIFICATE = "GIFT_CERTIFICATE", "문화상품권"
    CULTURE_GIFT_CERT = "CULTURE_GIFT_CERT", "도서문화상품권"
    GAME_GIFT_CERT = "GAME_GIFT_CERT", "게임문화상품권"

class PaymentStatusChoices(TextChoices):
    READY = "READY", "요청 생성"
    IN_PROGRESS = "IN_PROGRESS", "승인 중"
    WAITING_FOR_DEPOSIT = "WAITING_FOR_DEPOSIT", "입금 대기"
    DONE = "DONE", "승인 완료"
    CANCELED = "CANCELED",  "전체 취소"
    PARTIAL_CANCELED = "PARTIAL_CANCELED",  "부분 취소"
    ABORTED = "ABORTED", "승인 실패/중단"
    EXPIRED = "EXPIRED", "만료"

class CashReceiptTypeChoices(TextChoices):
    INCOME_DEDUCTION = "INCOME_DEDUCTION", "소득공제"
    EXPENSE_PROOF  = "EXPENSE_PROOF", "지출증빙"

class CashReceiptTransactionTypeChoices(TextChoices):
    CONFIRM = "CONFIRM", "발급"
    CANCEL = "CANCEL", "취소"

class CashReceiptIssueStatusChoices(TextChoices):
    IN_PROGRESS = "IN_PROGRESS", "발급 진행 중"
    COMPLETED = "COMPLETED", "발급 완료"
    FAILED = "FAILED", "발급 실패"