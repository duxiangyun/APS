/**
 * SSE 解析与事件归约（纯函数，便于单测）
 *
 * parseSseBuffer：把 SSE 文本缓冲区切成完整事件（保留残留分片）
 * reduceEvent：把一个 agent 事件归约到聊天条目 / 图表槽位
 */
import type { AgentEvent, ChartPayload, ChatItem, ToolCall } from "../types";
import { ganttFromToolResult, loadFromToolResult } from "./chart";

export interface SseParseResult {
  events: AgentEvent[];
  rest: string;
}

/** 按 \n\n 切分 SSE 块，解析 `data:` 行；返回事件列表与未完整残留 */
export function parseSseBuffer(buffer: string): SseParseResult {
  const events: AgentEvent[] = [];
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  for (const block of blocks) {
    for (const raw of block.split("\n")) {
      const line = raw.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (!payload || payload === "[DONE]") continue;
      try {
        events.push(JSON.parse(payload) as AgentEvent);
      } catch {
        /* 忽略不完整分片 */
      }
    }
  }
  return { events, rest };
}

export interface ReduceResult {
  item: ChatItem;
  chart?: ChartPayload;
  startedAt: Map<string, number>;
}

/** 事件归约：token 追加、tool_call 建卡、tool_result 回填、chart 更新槽位 */
export function reduceEvent(
  item: ChatItem,
  ev: AgentEvent,
  startedAt: Map<string, number>,
): ReduceResult {
  switch (ev.type) {
    case "token":
      return { item: { ...item, content: item.content + String(ev.content ?? "") }, startedAt };

    case "tool_call": {
      const name = String(ev.name ?? "");
      startedAt.set(name, Date.now());
      const call: ToolCall = {
        id: `${name}-${startedAt.get(name)}`,
        name,
        args: (ev.arguments ?? {}) as Record<string, unknown>,
        status: "running",
      };
      return { item: { ...item, tools: [...item.tools, call] }, startedAt };
    }

    case "tool_result": {
      const name = String(ev.name ?? "");
      const t0 = startedAt.get(name);
      const summary = String(ev.summary ?? "");
      const failed = /(^ERROR|失败|不存在)/.test(summary);
      const tools = [...item.tools];
      for (let i = tools.length - 1; i >= 0; i -= 1) {
        if (tools[i].name === name && tools[i].status === "running") {
          tools[i] = {
            ...tools[i],
            status: failed ? "error" : "ok",
            summary,
            data: ev.data as Record<string, unknown> | undefined,
            durationMs: t0 ? Date.now() - t0 : undefined,
          };
          break;
        }
      }
      // chart 事件优先；缺失时由工具结果兜底推导
      const data = ev.data as Record<string, unknown> | undefined;
      const derived = ganttFromToolResult(name, data) ?? loadFromToolResult(name, data) ?? undefined;
      return { item: { ...item, tools }, chart: derived, startedAt };
    }

    case "chart":
      return { item, chart: (ev.chart as ChartPayload | undefined) ?? undefined, startedAt };

    case "error":
      return { item: { ...item, error: String(ev.message ?? "服务异常") }, startedAt };

    default:
      return { item, startedAt };
  }
}
