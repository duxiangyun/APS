# APS 部署指南

基于 Docker Compose 的一键部署，适用于「本地 Mac 开发 → push 到 Git → 阿里云服务器一键部署」流程。

## 服务组成

| 服务 | 说明 | 端口 | 健康检查 |
|------|------|------|----------|
| aps | APS 智能排产后端 | 8000 | http://localhost:8000/open/health |
| agent | Web Agent 后端 | 8100 | http://localhost:8100/health |
| web | 前端（Vite 开发服务器） | 5173 | - |

数据持久化：

- `aps/data/db/aps_or.db` — APS 业务库（挂载到 aps 容器 `/app/data/db`）
- `agent/data/audit.db` — 审计日志库（挂载到 agent 容器 `/app/data`）

## 首次部署

```bash
# 1. 克隆代码
git clone https://github.com/duxiangyun/APS.git
cd APS

# 2. 创建环境变量文件（.env 不会提交 Git）
cp .env.example .env
vi .env        # 填写 LLM_API_KEY / LLM_BASE_URL 等

# 3. 赋予脚本可执行权限
chmod +x deploy.sh

# 4. 一键部署（含镜像构建）
./deploy.sh
```

## 日常更新

本地开发完成后：

```bash
# 本地
git add -A && git commit -m "xxx" && git push

# 服务器
cd /path/to/APS
./deploy.sh
```

`deploy.sh` 会自动完成：`git pull --ff-only` → 检查 `.env` → 备份数据库 →
清理 7 天前旧备份 → `docker compose build` → `docker compose up -d --remove-orphans`
→ 健康检查 → 输出服务地址。任一步骤失败立即退出。

## 快速重启（跳过镜像构建）

代码无变化、只想重启容器时：

```bash
./deploy.sh --quick
```

## 数据库备份与恢复

### 备份位置

- 每次部署自动备份到 `backups/YYYYMMDD_HHMMSS/`，包含：
  - `audit.db`（agent 审计库，如存在）
  - `aps_or.db`（APS 业务库，如存在）
- 自动清理 7 天前的旧备份。
- agent 容器每次启动迁移前，还会在 `agent/data/` 下用 `VACUUM INTO`
  生成 `audit_backup_YYYYMMDD_HHMMSS.db`。

### 手动恢复

```bash
# 停止服务
docker compose down

# 恢复 APS 业务库（将 <时间戳> 替换为实际目录名）
cp backups/<时间戳>/aps_or.db aps/data/db/aps_or.db

# 恢复 agent 审计库
cp backups/<时间戳>/audit.db agent/data/audit.db

# 重启
./deploy.sh --quick
```

## 数据库结构迁移

agent 容器启动时自动执行 `agent/migrate.py`（见 agent/Dockerfile 的 CMD）：

- 数据库不存在 → 创建完整表结构
- 数据库已存在 → 幂等的增量 `ALTER TABLE` 补齐缺失列（可重复执行）
- 迁移前自动 `VACUUM INTO` 备份，日志见：

```bash
docker compose logs agent   # 开头的 [migrate ...] 行即迁移日志
```

## 常见排查

```bash
docker compose ps                 # 查看容器与健康状态
docker compose logs -f aps        # aps 日志
docker compose logs -f agent      # agent 日志（含迁移日志）
curl http://localhost:8000/open/health
curl http://localhost:8100/health
```

注意：aps / agent 镜像内已安装 curl（healthcheck 依赖），修改 Dockerfile 后
首次部署需完整执行 `./deploy.sh`（不能用 `--quick`）以重建镜像。
