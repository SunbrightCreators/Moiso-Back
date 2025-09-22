#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/ubuntu/srv/ubuntu"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"

echo "[deploy] ensure docker installed"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update -y
  # 간단 설치: 우분투 기본 패키지로
  sudo apt-get install -y docker.io
  sudo systemctl enable --now docker
fi

echo "[deploy] choose compose CLI"
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"         # 최신 권장
else
  if ! command -v docker-compose >/dev/null 2>&1; then
    echo "[deploy] install docker-compose v1"
    sudo curl -fsSL \
      "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" \
      -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
  fi
  COMPOSE="docker-compose"
fi

echo "[deploy] host df before"; df -h || true
echo "[deploy] docker df before"; sudo docker system df || true

# 안전 정리 (미사용 리소스만 삭제)
sudo docker system prune -af || true
sudo docker builder prune -af || true
sudo find /var/lib/docker/containers -type f -name "*-json.log" -exec sudo truncate -s 0 {} \; || true

# (단독으로 떠있는 nginx가 80을 점유하면 충돌하므로 정리)
sudo docker ps --format '{{.Names}}' | grep -xq 'nginx' && { sudo docker stop nginx; sudo docker rm nginx; } || true

# 필요한 파일/경로 체크
if [ ! -f "$COMPOSE_FILE" ]; then
  echo "[deploy] ERROR: compose file not found at $COMPOSE_FILE" >&2
  exit 1
fi
if [ ! -d "$PROJECT_DIR" ]; then
  echo "[deploy] ERROR: project dir not found at $PROJECT_DIR" >&2
  exit 1
fi
if [ ! -f "$PROJECT_DIR/.env" ]; then
  echo "[deploy] WARNING: $PROJECT_DIR/.env not found (env_file가 .env를 참조한다면 생성 필요)"
fi

echo "[deploy] start compose up"
cd "$PROJECT_DIR"
sudo DOCKER_BUILDKIT=1 $COMPOSE -f "$COMPOSE_FILE" up -d --build

echo "[deploy] compose ps"
$COMPOSE -f "$COMPOSE_FILE" ps || true

echo "[deploy] smoke check"
curl -sI http://localhost || true

echo "[deploy] host df after"; df -h || true
echo "[deploy] docker df after"; sudo docker system df || true
