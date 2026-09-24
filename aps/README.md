# APS 智能排产系统（拆分后主服务）

原 APS 系统整体迁入本目录，业务逻辑未改动，仅调整了目录位置。

## 目录结构
- `src/web/`   FastAPI Web 服务（页面 + 原有 `/api/*` 接口 + 新增 `/open/*` 开放接口）
- `src/model/` 排产求解模型
- `src/etl/`   Excel → SQLite ETL
- `src/agent/` 内置排产助手（页面内 LLM 对话，`/agent` 路由）
- `data/db/aps_or.db`   SQLite 数据库
- `scripts/`   数据库工具脚本
- `docs/`      设计文档

## 启动

```bash
./start.sh          # 默认 0.0.0.0:8000，或 ./start.sh 8001
./stop.sh
```

手动方式（等价）：

```bash
cd src/web
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 页面入口:   http://127.0.0.1:8000/
- 接口文档:   http://127.0.0.1:8000/api-docs
- 开放 API:   `/open/*` 路由（见下方清单），Swagger 中 open-api 标签

## 新增开放 API（供 agent/ 调用）

`src/web/app/routers/open_api.py`，全部为只读查询（求解触发除外），业务逻辑零改动：

| 方法 | 路由 | 说明 |
|---|---|---|
| GET  | `/open/health` | 健康检查 |
| GET  | `/open/kpi/summary` | 最新批次核心 KPI |
| GET  | `/open/kpi/delivery` | 按优先级交付达成 / 准交率 |
| GET  | `/open/orders` | 需求订单列表（search/page/page_size） |
| GET  | `/open/orders/{order_id}` | 订单明细 |
| GET  | `/open/results/runs` | 求解批次列表 |
| GET  | `/open/results/views` | 结果视图清单 |
| GET  | `/open/results/{view_key}` | 结果明细（res_view_*） |
| GET  | `/open/equip-load` | 设备负荷（矩阵+明细） |
| GET  | `/open/iis` | IIS 不可行诊断 |
| POST | `/open/solve/start` | 触发求解 |
| GET  | `/open/solve/status` | 求解状态 |
