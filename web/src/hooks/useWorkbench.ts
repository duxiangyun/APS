/**
 * 工作台状态机：角色 / 技能开关 / 会话 / SSE 事件 / 图表槽位
 *
 * 闭环：提问 → token 增量渲染 → 工具卡片（tool_call/tool_result）→ 图表更新（chart）
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { agentApi, streamChat } from "../api";
import {
  ROLES,
  type AgentEvent,
  type ChartPayload,
  type ChartSlot,
  type ChatItem,
  type HealthInfo,
  type RoleKey,
  type Skill,
} from "../types";
import { reduceEvent } from "../utils/events";

const SESSION_KEY = "workbuddy.session_id";

/** UUID v4 格式校验（会话 ID 统一为 UUID v4，旧格式存储值自动迁移） */
const UUID_V4_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** 生成 UUID v4 会话/消息 ID（优先 crypto.randomUUID） */
function newId(): string {
  const c = window.crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  // fallback：手写 UUID v4（旧浏览器兼容）
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0;
    const v = ch === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function slotOf(chart: ChartPayload): ChartSlot {
  return chart.type === "gantt" ? "gantt" : chart.type === "kpi" ? "kpi" : "load";
}

export function useWorkbench() {
  const [role, setRole] = useState<RoleKey>("planner");
  const [skills, setSkills] = useState<Skill[]>([]);
  const [skillsError, setSkillsError] = useState<string | null>(null);
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [items, setItems] = useState<ChatItem[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [charts, setCharts] = useState<Partial<Record<ChartSlot, ChartPayload>>>({});
  const [activeTab, setActiveTab] = useState<ChartSlot | "kpi">("gantt");
  const [sessionId, setSessionId] = useState<string>(() => {
    // 旧格式（非 UUID v4）会话 ID 自动迁移为 UUID v4
    const saved = window.localStorage.getItem(SESSION_KEY);
    return saved && UUID_V4_RE.test(saved) ? saved : newId();
  });
  const abortRef = useRef<AbortController | null>(null);

  // -------------------------------------------------------------------------
  // 启动时加载技能（随角色切换重新拉取，白名单由 agent 侧 role_config 决定）
  // -------------------------------------------------------------------------
  useEffect(() => {
    window.localStorage.setItem(SESSION_KEY, sessionId);
  }, [sessionId]);

  useEffect(() => {
    let alive = true;
    agentApi
      .skills(role)
      .then((list) => {
        if (!alive) return;
        setSkills(list);
        setSkillsError(null);
        setEnabled(() => {
          const next: Record<string, boolean> = {};
          for (const s of list) next[s.name] = true;
          return next;
        });
      })
      .catch((e: Error) => alive && setSkillsError(e.message));
    return () => {
      alive = false;
    };
  }, [role]);

  const refreshHealth = useCallback(() => {
    agentApi
      .health()
      .then((h) => {
        setHealth(h);
        setHealthError(null);
      })
      .catch((e: Error) => setHealthError(e.message));
  }, []);

  useEffect(() => {
    refreshHealth();
    const timer = window.setInterval(refreshHealth, 20000);
    return () => window.clearInterval(timer);
  }, [refreshHealth]);

  // -------------------------------------------------------------------------
  const applyChart = useCallback((chart: ChartPayload) => {
    const slot = slotOf(chart);
    setCharts((prev) => ({ ...prev, [slot]: chart }));
    setActiveTab(slot);
  }, []);

  const updateItem = useCallback((id: string, patch: (item: ChatItem) => ChatItem) => {
    setItems((prev) => prev.map((it) => (it.id === id ? patch(it) : it)));
  }, []);

  const enabledSkills = useMemo(
    () => skills.filter((s) => enabled[s.name] !== false).map((s) => s.name),
    [skills, enabled],
  );

  // -------------------------------------------------------------------------
  // 图表钉选：固定当前图表，避免每次对话都刷新
  // -------------------------------------------------------------------------
  const [pinnedSlot, setPinnedSlot] = useState<ChartSlot | null>(null);

  const pinSlot = useCallback((slot: ChartSlot | null) => {
    setPinnedSlot(slot);
    // 切换钉选时自动切换到对应标签
    if (slot) setActiveTab(slot);
  }, [setActiveTab]);

  // -------------------------------------------------------------------------
  // 发送消息：SSE 事件 → 消息 / 工具卡片 / 图表
  // -------------------------------------------------------------------------
  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || streaming) return;

      const userId = newId();
      const botId = newId();
      setItems((prev) => [
        ...prev,
        { id: userId, kind: "user", content: message, tools: [], streaming: false },
        { id: botId, kind: "assistant", content: "", tools: [], streaming: true },
      ]);
      setStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;
      const startedAt = new Map<string, number>();

      try {
        await streamChat(
          {
            message,
            role: ROLES.find((r) => r.key === role)?.agentRole ?? "planner",
            session_id: sessionId,
            skills: enabledSkills,
          },
          (ev: AgentEvent) => {
            // 归约为新条目状态 + 可能的图表更新（纯函数，见 utils/events.ts）
            setItems((prev) =>
              prev.map((it) => {
                if (it.id !== botId) return it;
                const { item, chart } = reduceEvent(it, ev, startedAt);
                if (chart) {
                  const slot: ChartSlot = slotOf(chart);
                  // 若该槽位已被钉选，不更新（保留当前图表）
                  if (pinnedSlot !== slot) {
                    setCharts((c) => ({ ...c, [slot]: chart }));
                    setActiveTab(slot);
                  }
                }
                return item;
              }),
            );
          },
          controller.signal,
        );
      } catch (e) {
        const aborted = controller.signal.aborted;
        updateItem(botId, (it) => ({
          ...it,
          error: aborted ? "已中止本次回复" : `请求失败：${(e as Error).message}`,
        }));
      } finally {
        updateItem(botId, (it) => ({ ...it, streaming: false }));
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [applyChart, enabledSkills, role, sessionId, streaming, updateItem, pinnedSlot],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const resetSession = useCallback(() => {
    abortRef.current?.abort();
    setSessionId(newId());
    setItems([]);
    setCharts({});
    setActiveTab("gantt");
  }, []);

  const toggleSkill = useCallback((name: string, value: boolean) => {
    setEnabled((prev) => ({ ...prev, [name]: value }));
  }, []);

  return {
    role,
    setRole,
    skills,
    skillsError,
    enabled,
    toggleSkill,
    enabledSkills,
    health,
    healthError,
    refreshHealth,
    items,
    streaming,
    send,
    stop,
    resetSession,
    sessionId,
    charts,
    activeTab,
    setActiveTab,
    pinnedSlot,
    pinSlot,
    applyChart,
  };
}

export type Workbench = ReturnType<typeof useWorkbench>;
