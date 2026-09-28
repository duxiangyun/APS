/** 工作台共享类型定义 */

// ---------------------------------------------------------------------------
// 角色（前端状态模拟，不做登录）
// ---------------------------------------------------------------------------
/**
 * 9 个角色（与产品规划 6.4.2 权限矩阵、APS 侧 `app/constants.py::ROLE_MENUS`、
 * agent 侧 `app/role_config.py::ROLE_KEYS` 三处同源，顺序也保持一致）：
 *   切换角色 → ① 全局状态 role → agent /chat/stream + /skills 带新角色
 *             ② APS iframe src 带 ?role= → APS 侧 role_control.js 重新应用菜单权限
 */
export type RoleKey = "planner" | "supervisor" | "manager" | "analyst"
  | "purchaser" | "masterdata" | "sales" | "admin" | "default";

export interface RoleOption {
  key: RoleKey;
  label: string;
  desc: string;
  /** 映射到 agent /chat/stream 的 role 字段（agent 侧 persona） */
  agentRole: string;
}

export const ROLES: RoleOption[] = [
  { key: "planner", label: "生产计划员", desc: "关注订单交付与排产细节", agentRole: "planner" },
  { key: "supervisor", label: "车间主管", desc: "关注产能负荷与瓶颈异常", agentRole: "supervisor" },
  { key: "manager", label: "生产经理", desc: "关注 KPI、准交率与利润", agentRole: "manager" },
  { key: "analyst", label: "数据分析师", desc: "用数据定位延期与瓶颈原因", agentRole: "analyst" },
  { key: "purchaser", label: "采购员", desc: "关注物料齐套、到料时间与供应风险", agentRole: "purchaser" },
  { key: "masterdata", label: "主数据管理员", desc: "核对物料/设备/工艺/订单基础数据一致性", agentRole: "masterdata" },
  { key: "sales", label: "销售人员", desc: "对客交期承诺：能否按期交付与延期风险", agentRole: "sales" },
  { key: "admin", label: "IT 管理员", desc: "系统巡检、数据核对与审计", agentRole: "admin" },
  { key: "default", label: "访客", desc: "通用问答，仅开放 KPI 查询", agentRole: "default" },
];

/** 角色 key 顺序表（下拉/审计筛选共用，避免各处重复维护 9 个角色） */
export const ROLE_KEYS: RoleKey[] = ROLES.map((r) => r.key);

// ---------------------------------------------------------------------------
// 技能（GET /skills）
// ---------------------------------------------------------------------------
export interface SkillParam {
  type?: string;
  description?: string;
  enum?: string[];
}

export interface SkillSchema {
  type?: string;
  properties?: Record<string, SkillParam>;
  required?: string[];
}

export interface Skill {
  name: string;
  description: string;
  parameters?: SkillSchema;
  readonly?: boolean;
}

// ---------------------------------------------------------------------------
// 对话
// ---------------------------------------------------------------------------
export type ToolStatus = "running" | "ok" | "error";

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  status: ToolStatus;
  summary?: string;
  data?: Record<string, unknown>;
  durationMs?: number;
}

export type MessageKind = "user" | "assistant";

export interface ChatItem {
  id: string;
  kind: MessageKind;
  content: string;
  tools: ToolCall[];
  streaming: boolean;
  error?: string;
}

// ---------------------------------------------------------------------------
// 图表（SSE chart 事件）
// ---------------------------------------------------------------------------
export interface GanttDelivery {
  period: number;
  quantity: number;
  status?: string;
}

export interface GanttTask {
  name: string;
  start: number;
  end: number;
  due?: number | null;
  deliveries?: GanttDelivery[];
}

export type ChartSlot = "gantt" | "load" | "kpi";

// ---------------------------------------------------------------------------
// SSE 事件（agent /chat/stream）
// ---------------------------------------------------------------------------
export interface AgentEvent {
  type: "start" | "token" | "tool_call" | "tool_result" | "chart" | "done" | "error" | string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// APS 只读数据（经 agent 透传）
// ---------------------------------------------------------------------------
export interface HealthInfo {
  status?: string;
  service?: string;
  llm_configured?: boolean;
  llm_model?: string | null;
  llm_fallback_model?: string | null;
  aps_connected?: boolean;
  aps?: { status?: string; orders?: number; latest_run_id?: number | null };
  aps_error?: string;
}

export interface KpiSummary {
  run: Record<string, unknown> | null;
  kpi: Record<string, number | null>;
}

export interface DeliveryRow {
  priority_level: number;
  order_count_total: number;
  order_count_ontime: number;
  order_count_partial: number;
  order_count_delayed: number;
  order_count_undelivered: number;
  quantity_total: number;
  quantity_ontime: number;
  quantity_partial: number;
  quantity_delayed: number;
  quantity_undelivered: number;
}

export interface DeliveryInfo {
  run_id: number | null;
  ontime_rate: number | null;
  by_priority: DeliveryRow[];
}

export interface EquipLoad {
  run_id: number | null;
  matrix: Record<string, unknown>[];
  detail?: Record<string, unknown>[];
}

// ---------------------------------------------------------------------------
// 大模型配置（GET/POST /llm/config，POST /llm/test）
// ---------------------------------------------------------------------------
export interface LlmPreset {
  key: string;
  name: string;
  base_url: string;
  models: string[];
}

export interface LlmConfigPublic {
  base_url: string;
  model: string;
  fallback_model: string;
  temperature: number;
  max_tokens: number;
  has_api_key: boolean;
  api_key_masked: string;
  configured: boolean;
  presets: LlmPreset[];
}

export interface LlmTestResult {
  ok: boolean;
  latency_ms?: number;
  model?: string;
  reply?: string;
  message?: string;
}

// ---------------------------------------------------------------------------
// 审计日志（GET /audit/logs）
// ---------------------------------------------------------------------------
export interface AuditLogEntry {
  id: number;
  session_id: string;
  role: string;
  tool_name: string;
  params: Record<string, unknown>;
  result_summary: string;
  confirmed: boolean;
  status: "success" | "failed" | string;
  /** 本次调用是否命中 20s 短时缓存（阶段一止血新增） */
  cache_hit: boolean;
  duration_ms: number;
  created_at: string;
}

/** agent chart 事件中的 KPI 项 */
export interface KpiItem {
  key: string;
  label: string;
  value: number;
  unit: string;
  hint?: string;
  emphasize?: boolean;
  color?: string;
}

/** agent chart 事件中的 KPI 图表 */
export interface KpiChartPayload {
  type: "kpi";
  title: string;
  items: KpiItem[];
  delivery_by_priority?: DeliveryRow[];
  run_id?: number | null;
  profit_margin?: number;
}

/** agent chart 事件中的甘特图 */
export interface GanttChartPayload {
  type: "gantt";
  title: string;
  periods: number[];
  tasks: GanttTask[];
}

/** agent chart 事件中的负荷图 */
export interface LoadChartPayload {
  type: "load";
  title: string;
  periods: number[];
  resources: Array<{
    resource_code: string;
    capacity: number;
    peak_rate: number;
    avg_rate: number;
    total_load: number;
    normal_cost: number;
    periods: Record<string, number>;
  }>;
  highlight?: string[];
}

/** agent chart 事件（统一） */
export type ChartPayload = GanttChartPayload | LoadChartPayload | KpiChartPayload;
