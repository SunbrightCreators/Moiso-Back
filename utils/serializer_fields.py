from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.utils import timezone 
from rest_framework import serializers

class HumanizedDateTimeField(serializers.Field):
    def to_representation(self, value):
        if not isinstance(value, datetime):
            return value

        diff = relativedelta(timezone.now(), value)

        if diff.years:
            return f"{diff.years}년 전"
        elif diff.months:
            return f"{diff.months}개월 전"
        elif diff.weeks:
            return f"{diff.weeks}주 전"
        elif diff.days:
            return f"{diff.days}일 전"
        elif diff.hours:
            return f"{diff.hours}시간 전"
        elif diff.minutes:
            return f"{diff.minutes}분 전"
        else:
            return "방금 전"
