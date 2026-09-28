/**
 * 统一壳状态（React Context）：
 *   activeTab：'aps'（排产管理 iframe）| 'agent'（AI 助手工作台），默认 'aps'
 *   role：当前角色（与 activeTab 共用同一 Context，全局唯一），默认 'planner'
 * 切换 role 后：
 *   1) useWorkbench 负责重拉 /skills 并开启新会话（Agent 侧对话角色同步）
 *   2) App.tsx 的 APS iframe src 带 ?role= 重新加载（APS 侧菜单权限同步）
 */
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { ROLES, type RoleKey } from "../types";

/**
 * 初始角色：支持 `?role=masterdata` 深链（仅合法 key 生效，便于演示/直连），否则默认 planner。
 * 兼容 SSR（smoke.tsx 的 window 垫片没有 location）与非法值，任何异常都回退 planner。
 */
function resolveInitialRole(): RoleKey {
  try {
    const q = new URLSearchParams(window.location?.search ?? "").get("role");
    return ROLES.some((r) => r.key === q) ? (q as RoleKey) : "planner";
  } catch {
    return "planner";
  }
}

export type AppTab = "aps" | "agent";

interface AppShellState {
  activeTab: AppTab;
  setActiveTab: (tab: AppTab) => void;
  role: RoleKey;
  setRole: (role: RoleKey) => void;
}

const AppShellContext = createContext<AppShellState | null>(null);

export function AppShellProvider({ children }: { children: ReactNode }) {
  const [activeTab, setActiveTab] = useState<AppTab>("aps");
  const [role, setRole] = useState<RoleKey>(resolveInitialRole);
  const value = useMemo(() => ({ activeTab, setActiveTab, role, setRole }), [activeTab, role]);
  return <AppShellContext.Provider value={value}>{children}</AppShellContext.Provider>;
}

export function useAppShell(): AppShellState {
  const ctx = useContext(AppShellContext);
  if (!ctx) throw new Error("useAppShell 必须在 AppShellProvider 内使用");
  return ctx;
}

