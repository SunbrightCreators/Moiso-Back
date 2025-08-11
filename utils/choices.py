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
