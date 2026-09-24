/**
 * Agent 后端（8100）API 封装 —— 前端唯一上游，绝不直连 APS。
 *
 * 基础地址来自环境变量 VITE_AGENT_BASE_URL（见 .env.example）：
 *   /agent（默认）        同源相对路径，由 vite 代理转发到 agent，无需 CORS
 *   http://127.0.0.1:8100 直连 agent（agent 已开启 CORS）
 */
import type {
  AgentEvent,
  AuditLogEntry,
  DeliveryInfo,
  EquipLoad,
  HealthInfo,
  KpiSummary,
  LlmConfigPublic,
  LlmTestResult,
  Skill,
} from "./types";

const RAW_BASE = (import.meta.env.VITE_AGENT_BASE_URL || "/agent").trim();
export const AGENT_BASE = RAW_BASE.replace(/\/+$/, "");

function url(path: string): string {
  return `${AGENT_BASE}${path}`;
}

async function errorText(resp: Response): Promise<string> {
  try {
    const body = (await resp.json()) as { detail?: unknown; message?: unknown };
    return String(body.detail ?? body.message ?? `HTTP ${resp.status}`);
  } catch {
    return `HTTP ${resp.status}`;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(url(path));
  if (!resp.ok) throw new Error(await errorText(resp));
  return (await resp.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(url(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(await errorText(resp));
  return (await resp.json()) as T;
}

export const agentApi = {
  /** GET /health */
  health: () => getJson<HealthInfo>("/health"),
  /** GET /skills?role=xxx 按角色白名单过滤技能 */
  skills: async (role?: string): Promise<Skill[]> => {
    const q = role ? `?role=${encodeURIComponent(role)}` : "";
    const data = await getJson<{ skills: Skill[] }>(`/skills${q}`);
    return data.skills ?? [];
  },
  /** POST /tools/{name} 工具直查（调试用，不经 LLM） */
  tool: <T>(name: string, args: Record<string, unknown> = {}) =>
    postJson<T>(`/tools/${name}`, args),
  /**
   * APS 只读数据经 agent 透传（agent 的 /api/aps/open/* 兼容路由），
   * 保证前端只与 agent 通信。
   */
  aps: {
    kpiSummary: () => getJson<KpiSummary>("/api/aps/open/kpi/summary"),
    kpiDelivery: () => getJson<DeliveryInfo>("/api/aps/open/kpi/delivery"),
    equipLoad: () => getJson<EquipLoad>("/api/aps/open/equip-load"),
  },
  // -----------------------------------------------------------------------
  // 大模型配置
  // -----------------------------------------------------------------------
  llm: {
    /** GET /llm/config 当前配置（Key 脱敏）+ 预设 */
    config: () => getJson<LlmConfigPublic>("/llm/config"),
    /** POST /llm/config 保存配置（api_key 为空表示保留原值） */
    save: (cfg: Partial<LlmConfigPublic> & { api_key?: string }) =>
      postJson<{ ok: boolean; config: LlmConfigPublic }>("/llm/config", cfg),
    /** POST /llm/test 连通性测试 */
    test: (probe: { base_url: string; api_key?: string; model: string }) =>
      postJson<LlmTestResult>("/llm/test", probe),
  },
  // -----------------------------------------------------------------------
  // 审计日志
  // -----------------------------------------------------------------------
  audit: {
    /** GET /audit/logs?session_id=&role=&tool=&limit= */
    logs: (params: { session_id?: string; role?: string; tool?: string; limit?: number } = {}) => {
      const qs = new URLSearchParams();
      if (params.session_id) qs.set("session_id", params.session_id);
      if (params.role) qs.set("role", params.role);
      if (params.tool) qs.set("tool", params.tool);
      if (params.limit) qs.set("limit", String(params.limit));
      const q = qs.toString();
      return getJson<{ count: number; logs: AuditLogEntry[] }>(`/audit/logs${q ? `?${q}` : ""}`);
    },
  },
};

// ---------------------------------------------------------------------------
// SSE 流式对话
// ---------------------------------------------------------------------------
export interface ChatStreamBody {
  message: string;
  role: string;
  session_id?: string;
  /** 已启用的技能名（agent 侧据此裁剪可用工具，缺省为全部） */
  skills?: string[];
}

/**
 * POST /chat/stream
 * 逐条回调 SSE 事件：start / token / tool_call / tool_result / chart / done / error
 */
export async function streamChat(
  body: ChatStreamBody,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(url("/chat/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!resp.ok || !resp.body) throw new Error(await errorText(resp));

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      for (const raw of block.split("\n")) {
        const line = raw.trim();
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (!payload || payload === "[DONE]") continue;
        try {
          onEvent(JSON.parse(payload) as AgentEvent);
        } catch {
          /* 忽略不完整分片 */
        }
      }
    }
  }
}

export function fmtNumber(v: unknown, digits = 0): string {
  const n = Number(v);
  if (v === null || v === undefined || Number.isNaN(n)) return "-";
  return n.toLocaleString("zh-CN", { maximumFractionDigits: digits });
}
