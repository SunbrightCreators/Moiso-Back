#!/bin/bash
set -euo pipefail

# Docker 설치 여부 확인, 없다면 설치
if ! type docker > /dev/null
then
  echo "docker does not exist"
  echo "Start installing docker"
  sudo apt-get update
  sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
  sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu bionic stable"
  sudo apt update
  apt-cache policy docker-ce
  sudo apt install -y docker-ce
fi

# Docker Compose 설치 여부 확인, 없다면 설치
if ! type docker-compose > /dev/null
then
  echo "docker-compose does not exist"
  echo "Start installing docker-compose"
  sudo curl -L "https://github.com/docker/compose/releases/download/1.27.3/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
fi

# fastText ko 모델 호스트에 사전 설치 (inline)
############################################
MODEL_DIR="/home/ubuntu/ft_models"
MODEL_BIN="${MODEL_DIR}/cc.ko.300.bin"
MODEL_GZ="${MODEL_BIN}.gz"
MODEL_URL="https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.ko.300.bin.gz"

# 도구 준비
if ! command -v wget >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y wget
fi
if ! command -v gunzip >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y gzip
fi

# 디렉토리/권한
sudo mkdir -p "${MODEL_DIR}"
sudo chown -R ubuntu:ubuntu "${MODEL_DIR}"

# 없으면 다운로드+압축해제, 있으면 스킵
if [ ! -f "${MODEL_BIN}" ]; then
  echo "[INFO] fastText ko 모델 다운로드 시작..."
  tmp="${MODEL_GZ}.part"
  wget -O "${tmp}" "${MODEL_URL}"
  mv "${tmp}" "${MODEL_GZ}"
  gunzip -f "${MODEL_GZ}"
  sudo chmod 644 "${MODEL_BIN}"
  echo "[INFO] fastText 모델 준비 완료: ${MODEL_BIN}"
else
  echo "[INFO] fastText 모델 이미 존재: ${MODEL_BIN}"
fi

ls -lh "${MODEL_BIN}" || true

# Docker Compose로 서버 빌드 및 실행 (docker-compose.prod.yml 사용)
echo "start docker-compose up: ubuntu"
sudo docker-compose -f /home/ubuntu/srv/ubuntu/docker-compose.prod.yml up --build -d