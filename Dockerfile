FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Seoul

WORKDIR /home/app/web

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ \
    cmake \                    
    libpq-dev \
    libjpeg-dev zlib1g-dev \
    tzdata \
 && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel

COPY requirements.txt .

# pip/빌드툴 최신화
RUN python -m pip install --upgrade pip setuptools wheel

# 1) numpy를 먼저 설치
RUN pip install --no-cache-dir "numpy==1.26.4"

# 2) build isolation을 끄고 나머지 의존성 설치
RUN pip install --no-cache-dir --no-build-isolation -r requirements.txt

COPY . .

# 기본 실행은 compose에서 지정(runserver 등)

