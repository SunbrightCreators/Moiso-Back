# 패키지 초기화 단계에서 __init__.py가 from .base import DEBUG 를 실행하면서 .base를 무조건 임포트해버림. 
# .env/환경변수 준비 전이라도 SECRET_KEY = env('SECRET_KEY')가 바로 실행되어 실패한다.
