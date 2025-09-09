from functools import wraps
from rest_framework.exceptions import ValidationError

def require_query_params(*required_query_params:str):
    """
    클라이언트가 필수 쿼리 파라미터를 포함하여 요청했는지 확인합니다.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            errors = dict()

            for param in required_query_params:
                if not request.query_params.get(param):
                    errors[param] = "This query parameter is required."

            if errors:
                raise ValidationError(errors)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def validate_path_choices(**path_variables):
    """
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
                raise ValidationError(errors)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
