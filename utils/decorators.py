from functools import wraps
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from utils.choices import ProfileChoices

def example(func):
    """
    예시 코드입니다.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # 여기에 데코레이터 코드를 작성하세요.
        return func(self, *args, **kwargs)
    return wrapper

def validate_data(service_func):
    """
    클라이언트가 전송한 데이터가 유효한지 검증합니다.
    Service에서 사용해 주세요.
    """
    @wraps(service_func)
    def wrapper(self, *args, **kwargs):
        if not self.serializer.is_valid():
            return Response(
                self.serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        return service_func(self, *args, **kwargs)
    return wrapper

def validate_permission(service_func):
    """
    클라이언트가 해당 인스턴스에 대하여 요청을 수행할 권한을 갖고 있는지 검증합니다.
    Service에서 사용해 주세요.
    """
    @wraps(service_func)
    def wrapper(self, *args, **kwargs):
        if self.instance.user != self.request.user:
            return Response(
                {"detail":"권한이 없습니다."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return service_func(self, *args, **kwargs)
    return wrapper

def validate_unique(service_func):
    """
    클라이언트의 요청이 UNIQUE 제약조건을 준수하는지 검증합니다.
    Service에서 사용해 주세요.
    """
    @wraps(service_func)
    def wrapper(self, *args, **kwargs):
        try:
            return service_func(self, *args, **kwargs)
        except IntegrityError as error:
            if "UNIQUE constraint failed" in str(error):
                return Response(
                    {"detail":"이미 존재하는 값입니다."},
                    status=status.HTTP_409_CONFLICT,
                )
    return wrapper

def require_query_params(*required_query_params:str):
    """
    클라이언트가 필수 쿼리 파라미터를 포함하여 요청했는지 확인합니다.
    View에서 사용해 주세요.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            errors = dict()

            for param in required_query_params:
                if not request.query_params.get(param):
                    errors[param] = "This query parameter is required."

            if errors:
                return Response(
                    errors,
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def validate_path_choices(**path_variables):
    """
    View에서 사용해 주세요.
    Examples:
        validate_path_choices(profile=ProfileChoices.values)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            errors = dict()

            for var_name, values in path_variables.items():
                if var_name not in kwargs:
                    errors[var_name] = "This path variable is required."
                elif kwargs[var_name] not in values:
                    errors[var_name] = f"Ensure this value has one of these: {', '.join(str(value) for value in values)}"

            if errors:
                return Response(
                    errors,
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def require_profile(profile:ProfileChoices):
    """
    Service에서 사용해 주세요.
    """
    def decorator(service_func):
        @wraps(service_func)
        def wrapper(self, *args, **kwargs):
            if getattr(self.request.user, profile.value, None) is None:
                raise PermissionDenied(f"{profile.label} 프로필을 생성해 주세요.")
            return service_func(self, *args, **kwargs)
        return wrapper
    return decorator
