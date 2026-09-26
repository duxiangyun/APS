#!/usr/bin/env bash
# APS 一键部署脚本（本地 / 阿里云服务器通用）
# 用法:
#   ./deploy.sh          完整部署：拉代码 → 检查 .env → 备份数据库 → 构建 → 启动 → 健康检查
#   ./deploy.sh --quick  跳过镜像构建，只重启容器
set -euo pipefail

cd "$(dirname "$0")"

QUICK=0
for arg in "$@"; do
  case "$arg" in
    --quick) QUICK=1 ;;
    -h|--help)
      echo "用法: ./deploy.sh [--quick]"
      echo "  --quick  跳过 docker compose build，仅重启容器"
      exit 0
      ;;
    *)
      echo "[错误] 未知参数: $arg（仅支持 --quick）" >&2
      exit 1
      ;;
  esac
done

log() { printf '\n==> %s\n' "$*"; }

# ---------- 1. 拉取最新代码 ----------
log "1/8 拉取最新代码 (git pull --ff-only)"
git pull --ff-only

# ---------- 2. 检查 .env ----------
log "2/8 检查 .env 配置文件"
if [ ! -f .env ]; then
  echo "[错误] 未找到 .env 文件，部署中止。" >&2
  echo "       首次部署请执行: cp .env.example .env && vi .env" >&2
  exit 1
fi

# ---------- 3. 备份数据库 ----------
log "3/8 备份数据库到 backups/"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="backups/${TS}"
mkdir -p "${BACKUP_DIR}"

backup_db() {
  local db_path="$1"
  if [ -f "${db_path}" ]; then
    cp "${db_path}" "${BACKUP_DIR}/$(basename "${db_path}")"
    echo "    已备份: ${db_path} -> ${BACKUP_DIR}/"
  else
    echo "    跳过（文件不存在）: ${db_path}"
  fi
}

backup_db "agent/data/audit.db"
backup_db "aps/data/db/aps_or.db"

# ---------- 4. 清理旧备份 ----------
log "4/8 清理 7 天前的旧备份"
if [ -d backups ]; then
  find backups -mindepth 1 -maxdepth 1 -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true
fi
echo "    现存备份: $(find backups -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ') 个"

# ---------- 5. 构建镜像 ----------
log "5/8 构建镜像"
if [ "${QUICK}" -eq 1 ]; then
  echo "    --quick: 跳过构建"
else
  docker compose build
fi

# ---------- 6. 启动容器 ----------
log "6/8 启动容器 (docker compose up -d --remove-orphans)"
docker compose up -d --remove-orphans

# ---------- 7. 健康检查（失败只警告，不退出） ----------
log "7/8 健康检查"
health_check() {
  local name="$1" url="$2" i
  for i in $(seq 1 10); do
    if curl -fsS --max-time 3 -o /dev/null "${url}" 2>/dev/null; then
      echo "    [OK]   ${name}: ${url}"
      return 0
    fi
    sleep 3
  done
  echo "    [警告] ${name} 健康检查失败: ${url}"
  echo "           排查: docker compose ps | docker compose logs ${name}"
  return 0
}

health_check "aps"   "http://localhost:8000/open/health"
health_check "agent" "http://localhost:8100/health"

# ---------- 8. 部署完成 ----------
log "8/8 部署完成"
cat <<EOF
  APS 后端   : http://localhost:8000   (健康检查 /open/health)
  Agent 后端 : http://localhost:8100   (健康检查 /health)
  Web 前端   : http://localhost:5173
  数据库备份 : ${BACKUP_DIR}/
EOF
