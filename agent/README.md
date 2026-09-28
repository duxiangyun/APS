# Web Agent 后端（FastAPI, 端口 8100）

APS 的独立 Web Agent 后端：**轻量 ReAct 循环**（自研，未用 LangGraph——工具仅 4 个只读查询，单层循环足够）+ **SSE 流式输出** + **只读工具层**（通过 HTTP 调用 aps `/open/*`，不 import aps 内部模块）。

## 架构

```
web (5173) ──▶ agent (8100, FastAPI)
                 ├─ POST /chat/stream   ReAct 循环（LLM function calling）
                 ├─ GET  /skills        技能清单（前端左侧栏）
                 ├─ GET  /health        健康检查
                 ├─ POST /tools/{name}  工具直查（调试/降级）
                 └─ HTTP /open/* ──▶ aps (8000)
```

## 接口

| 方法 | 路由 | 说明 |
|---|---|---|
| POST | `/chat/stream` | SSE 流式对话，事件：start / token / tool_call / tool_result / chart / done（异常时 error） |
| GET  | `/skills` | 4 个只读技能及 JSON Schema（前端左侧栏展示与勾选） |
| GET  | `/health` | 健康检查（APS 连通性、LLM 配置） |
| POST | `/tools/{name}` | 工具直查（不经 LLM） |

### POST /chat/stream

请求：

```json
{ "message": "订单7的排产计划是怎么安排的？", "role": "planner",
  "session_id": "web1", "skills": ["get_schedule"] }
```

- `skills`：前端勾选启用的技能名（缺省为全部）；未启用的工具既不提供给 LLM 也不允许降级直查
- 响应为 `text/event-stream`，`event.type` 取值（统一契约）：`start`（会话 / 模型配置）·
  `token`（回答文本增量，**LLM 模式与降级模式统一推 `token`，不再出现 `delta`**）·
  `tool_call` · `tool_result` · `chart` · `done`；发生异常时补发 `error`（其后仍以 `data: [DONE]` 收尾）。
  末尾固定 `data: [DONE]`。`chart` 事件负载结构：

```json
{"type":"chart","session_id":"web1","name":"get_schedule",
 "chart":{"type":"gantt","title":"订单7 交付甘特图（周期）","tasks":[{"name":"订单7 MN-TM3G2A4",
          "start":1,"end":5,"due":5,"deliveries":[{"period":5,"quantity":45}]}],"periods":[1,2,3,4,5]}}
```

工具（全部只读，均带 JSON Schema，调用记录写入 `logs/tool_calls.jsonl`：session_id/工具名/参数/耗时/结果摘要）：
`get_orders(status, due_before)` · `get_schedule(order_id)` · `get_machine_load(period, resource)` ·
`get_bottleneck(period, top_n)` · `explain_delay(order_id)` · `get_kpi()` · `get_audit_logs(...)`（仅 admin） ·
`get_system_status()`（仅 admin） ·
`get_material_master(code, search, category)` · `get_bom(parent_material_code, max_level)` ·
`get_routing(material_code, routing_id)` · `get_resource_master(code, type, page, page_size)`
（后 4 个为主数据只读工具，数据源 aps `/open/md/*`，授权给 masterdata 角色）

## LLM 配置（OpenAI 兼容）

```bash
cp .env.example .env   # 填 LLM_API_KEY
```

- `LLM_MODEL` 默认 `glm-4.7-flash`
- 失败策略：429 / 5xx / 错误码 1305 → 自动重试一次 → 仍失败切换 `LLM_FALLBACK_MODEL`
- **未配置 API Key 时进入降级模式**：`/chat/stream` 仍按同一事件流输出（关键词识别意图 → 直查工具 → 推送
  tool_call / tool_result / chart 事件），因此前端「提问 → 流式回复 → 工具卡片 → 图表更新」闭环无需 API Key 即可验证

## 自检

```bash
python3 scripts/check_sse.py "订单2为什么延期？"   # 自定义单问
python3 scripts/check_sse.py            # 4 个示例问题，校验事件流 / 工具 / 图表
python3 scripts/check_roles.py          # 同一问题在 manager / planner 下的回答差异
```

## 角色差异（回答裁剪）

角色配置集中在 `app/role_config.py`（单一事实来源），三处共同保证「同一问题不同角色不同回答」：

| 机制 | 位置 | 作用 |
|---|---|---|
| 工具白名单 | `ROLES[*].allowed_tools` | manager 具备 `explain_delay` 订单级归因能力，但工具集合与 planner 不同 |
| field_filter 字段白名单 | `_FIELD_FILTERS`（`apply_field_filter`） | manager 只回传结论级字段（`explain_delay`→order_id/delay_reason/delay_periods/penalty，`get_schedule`→order_id/due_period/delivery_rate/overall_span），屏蔽设备工序段/设备明细/期次明细 |
| 回答规则 + few-shot | `_RULES_TEMPLATE` / `output_style["example"]` | 结论先行、多工具结果综合、无法回答给替代建议、禁止堆砌工具结果；每个角色带输出示例 |

裁剪只作用于回传 LLM 的 `as_text`：前端 tool 卡片的 `data` / `chart` 保持完整供人工核查。

## 启动

```bash
pip install -r requirements.txt
./start.sh              # 0.0.0.0:8100
./stop.sh
```

前提：APS 服务已运行（`APS_BASE_URL`，默认 `http://127.0.0.1:8000`）。

