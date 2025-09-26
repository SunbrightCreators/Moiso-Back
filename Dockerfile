# Debian slim 기반: 과학 스택(NumPy/Scipy/Sklearn/kiwi/fasttext) 빌드 호환성↑
FROM python:3.12-slim

# 파이썬 런타임 편의/일관성
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Seoul

# 작업 디렉토리
WORKDIR /app

# 시스템 의존성
# - libpq-dev: (psycopg2-binary는 없어도 되지만 있어도 무방)
# - libjpeg-dev, zlib1g-dev: Pillow
# - libgomp1, libstdc++6: fasttext, sklearn/numba 등 OpenMP/CPP 런타임
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc g++ \
    libpq-dev \
    libjpeg-dev zlib1g-dev \
    cmake ninja-build \
    libgomp1 libstdc++6 \
    tzdata \
 && rm -rf /var/lib/apt/lists/*

# pip / setuptools / wheel 버전 고정(네 요구사항에 맞춤)
RUN python -m pip install --upgrade "pip==25.2" "setuptools==80.9.0" wheel

# 의존성 설치: 대규모 빌드 가속 위해 numpy 먼저
COPY requirements.txt /app/requirements.txt
RUN pip install "numpy==1.26.4"
RUN pip install --no-build-isolation -r requirements.txt

# 비루트 유저
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# 앱 소스 복사
COPY . /app/

# (옵션) 기본 포트 노출 — gunicorn 8000 사용 시
EXPOSE 8000

# 실행 명령은 docker-compose나 ECS에서 지정
# 예) gunicorn configs.wsgi:application --bind 0.0.0.0:8000
