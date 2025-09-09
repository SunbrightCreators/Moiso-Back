from functools import wraps
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from utils.choices import ProfileChoices

def validate_data(service_func):
    """
    클라이언트가 전송한 데이터가 유효한지 검증합니다.
    """
    @wraps(service_func)
    def wrapper(self, *args, **kwargs):
        if not self.serializer.is_valid():
            raise ValidationError(self.serializer.errors)
        return service_func(self, *args, **kwargs)
    return wrapper

def validate_permission(service_func):
    """
    클라이언트가 해당 인스턴스에 대하여 요청을 수행할 권한을 갖고 있는지 검증합니다.
    """
    @wraps(service_func)
    def wrapper(self, *args, **kwargs):
        if self.instance.user != self.request.user:
            raise PermissionDenied(detail="권한이 없어요.")
        return service_func(self, *args, **kwargs)
    return wrapper

def require_profile(profile:ProfileChoices):
    """
    Service에서 사용해 주세요.
    """
    def decorator(service_func):
        @wraps(service_func)
        def wrapper(self, *args, **kwargs):
            if getattr(self.request.user, profile.value, None) is None:
                raise PermissionDenied(detail=f"{profile.label} 프로필을 생성해 주세요.")
            return service_func(self, *args, **kwargs)
        return wrapper
    return decorator

def validate_unique(service_func):
    """
    클라이언트의 요청이 UNIQUE 제약조건을 준수하는지 검증합니다.
    """
    @wraps(service_func)
    def wrapper(self, *args, **kwargs):
        try:
            return service_func(self, *args, **kwargs)
        except IntegrityError as error:
            if "UNIQUE constraint failed" in str(error):
                raise Response(
                    data={"detail":"이미 존재하는 값입니다."},
                    status=status.HTTP_409_CONFLICT,
                )
    return wrapper
