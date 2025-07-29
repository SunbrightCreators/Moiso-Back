from django.db.models import IntegerChoices

class ExampleChoices(IntegerChoices):
    ONE = 1, '일'
    TWO = 2, '이'
    THREE = 3, '삼'