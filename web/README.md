# Web Agent 前端（React + Vite + TypeScript）

APS WorkBuddy 风格三栏工作台：通过 agent 后端（8100）访问 APS 数据，**不直连 APS**。

## 技术栈

| 用途 | 选型 |
| --- | --- |
| 框架 | React 18 + TypeScript + Vite 6 |
| UI 组件 | Ant Design 5（Layout / Button / Card / Segmented / Collapse…） |
| 图表 | ECharts 5（按需注册，甘特图用 `custom` 自定义系列） |
| Markdown | react-markdown |
| 流式 | 原生 fetch + ReadableStream 解析 SSE（无额外依赖） |

## 布局（WorkBuddy 风格三栏）

```
┌──────────┬────────────────────────────┬───────────────────┐
│ 左 240px │ 中 自适应                   │ 右 480px（可折叠） │
│ 角色切换 │ 对话消息（Markdown 渲染）    │ Tabs：            │
│ 技能开关 │ 工具调用折叠卡片            │  甘特图           │
│ 连接状态 │  工具名+参数+结果摘要        │  设备负荷         │
│ 设置入口 │ 输入框（Enter 发送）         │  KPI              │
└──────────┴────────────────────────────┴───────────────────┘
```

- 角色切换为前端状态模拟（无登录），并作为 `role` 传给 agent 影响回答风格
- 技能列表来自 `GET /skills`，勾选后随请求 `skills` 字段下发（agent 侧据此裁剪可用工具）
- 右侧栏收到 SSE `chart` 事件时自动切换到对应标签页并渲染图表；无数据时显示占位甘特图/负荷图

## 目录结构

```
web/
├── index.html
├── vite.config.ts              # 5173 端口 + /agent、/api 代理 + 拆包配置
├── .env.example / .env.development
├── package.json / tsconfig.json
└── src/
    ├── main.tsx                # ConfigProvider（zh_CN 主题）
    ├── App.tsx                 # 三栏布局骨架
    ├── api.ts                  # agent API 封装（含 SSE 解析）
    ├── types.ts                # 角色 / 技能 / 消息 / 图表 类型
    ├── styles.css
    ├── hooks/
    │   └── useWorkbench.ts     # 状态机：角色·技能·会话·SSE 事件·图表槽位
    ├── utils/
    │   ├── echarts.ts          # ECharts 按需注册
    │   ├── events.ts           # SSE 解析 + 事件归约（纯函数，可单测）
    │   └── chart.ts            # 工具结果 → 图表数据 / 占位数据
    └── components/
        ├── LeftPanel.tsx       # 角色 / 技能 / 状态 / 设置
        ├── ChatPanel.tsx       # 消息列表 + 输入框
        ├── MessageItem.tsx     # 单条消息（Markdown + 工具卡片）
        ├── ToolCallCard.tsx    # 工具调用折叠卡片
        ├── RightPanel.tsx      # 甘特图 / 负荷 / KPI 标签页
        ├── EChart.tsx          # ECharts 生命周期封装
        └── charts/
            ├── GanttChart.tsx  # custom 系列甘特图 + 交付散点 + 交期虚线
            ├── LoadChart.tsx   # 负荷柱状图 + 产能线
            └── KpiPanel.tsx    # KPI 指标卡 + 按优先级交付表

scripts/smoke.tsx             # 冒烟自检脚本（npm run smoke）
```

## SSE 事件 → UI 映射

| 事件 | 前端行为 |
| --- | --- |
| `start` | 记录会话信息（LLM 是否配置） |
| `token` | 追加到当前助手消息，Markdown 实时渲染 |
| `tool_call` | 新增工具卡片（执行中），展示工具名与参数 |
| `tool_result` | 卡片转为成功/失败，补充结果摘要、原始数据、耗时 |
| `chart` | 写入右侧对应槽位（`gantt` → 甘特图，`bar` → 设备负荷）并自动切换标签页、展开右栏 |
| `done` / `[DONE]` | 结束本轮，恢复输入框 |


## 端口与环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| 端口 | `5173` | vite dev server |
| `VITE_AGENT_BASE_URL` | `/agent` | Agent 后端地址；相对路径由 vite 代理转发（无 CORS） |
| `VITE_PROXY_TARGET` | `http://127.0.0.1:8100` | 代理目标（容器内为 `http://agent:8100`） |

复制 `.env.example` 为 `.env.local` 可按需覆盖。若想让浏览器直连 agent（agent 已开 CORS），设 `VITE_AGENT_BASE_URL=http://127.0.0.1:8100`。

## 启动

```bash
cd web
npm install
npm run dev            # http://localhost:5173

npm run typecheck      # tsc --noEmit
npm run smoke          # 冒烟自检：渲染 + 图表 + 真实 SSE 闭环（需 agent 已启动）
npm run build          # 产物体积检查 → dist/
npm run preview        # 预览生产构建
```

构建产物（gzip 后）：`antd 264K` / `echarts 183K`（按需注册）/ `react 46K` / `markdown 36K` / 业务 10K。

## 启动顺序

1. `aps/start.sh` —— 8000，APS 数据与 `/open/*` 开放接口
2. `agent/start.sh` —— 8100，Agent 后端（SSE / 工具）
3. `cd web && npm run dev` —— 5173，本工作台

或 `docker compose up -d` 一键启动三个服务。

## 闭环验证（提问 → 流式回复 → 工具卡片 → 图表更新）

未配置 LLM 时 agent 走降级模式，仍会推送 `tool_call` / `tool_result` / `chart` 事件，因此闭环可直接验证。在输入框依次尝试：

| 示例问题 | 预期效果 |
| --- | --- |
| `订单7的排产计划是怎么安排的？` | 工具卡片 `get_schedule` + 右侧甘特图更新 |
| `查看涂装车间的设备负荷` | 工具卡片 `get_machine_load` + 右侧设备负荷图更新 |
| `有哪些订单延期了？` | 工具卡片 `get_orders`，回复列出延期订单 |
| `订单2为什么延期？` | 工具卡片 `explain_delay` + `get_schedule`，含归因与罚金（manager 角色回复为结论级 + KPI 影响，不含工序明细） |

agent 侧也可用 `python3 agent/scripts/check_sse.py` 做同样的无人值守自检（4/4 通过），
`python3 agent/scripts/check_roles.py` 校验同一问题在 manager / planner 下的回答差异（2/2 通过）。

