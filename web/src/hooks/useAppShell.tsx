/**
 * 统一壳状态（React Context）：
 *   activeTab：'aps'（排产管理 iframe）| 'agent'（AI 助手工作台），默认 'aps'
 *   role：当前角色（与 activeTab 共用同一 Context，全局唯一）
 * 切换 role 后由 useWorkbench 负责重拉 /skills 并开启新会话。
 */
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { RoleKey } from "../types";

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
  const [role, setRole] = useState<RoleKey>("planner");
  const value = useMemo(() => ({ activeTab, setActiveTab, role, setRole }), [activeTab, role]);
  return <AppShellContext.Provider value={value}>{children}</AppShellContext.Provider>;
}

export function useAppShell(): AppShellState {
  const ctx = useContext(AppShellContext);
  if (!ctx) throw new Error("useAppShell 必须在 AppShellProvider 内使用");
  return ctx;
}

