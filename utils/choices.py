from django.db.models import IntegerChoices, TextChoices

class ExampleChoices(IntegerChoices):
    '''
    예시 코드입니다.
    '''
    ONE = 1, '일'
    TWO = 2, '이'
    THREE = 3, '삼'

class GenderChoices(TextChoices):
    FEMALE = 'F', '여성'
    MALE = 'M', '남성'
    NONE = 'N', '선택 안함'
