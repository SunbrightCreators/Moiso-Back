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

# Docker Compose로 서버 빌드 및 실행 (docker-compose.prod.yml 사용)
echo "start docker-compose up: ubuntu"
sudo docker-compose -f /home/ubuntu/srv/ubuntu/docker-compose.prod.yml up --build -d