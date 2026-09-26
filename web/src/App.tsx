/**
 * 统一入口壳（第一步骨架）
 *   顶部 56px 标题栏：Logo + "APS 智能排产" | Tab「排产管理 / AI 助手」| 右侧留空
 *   内容区按 activeTab 切换：
 *     'aps'   → iframe 嵌入 APS（相对路径 /aps，由 vite 反向代理转发到 APS 后端，
 *               避免写死 localhost 导致部署到服务器后指向用户本机），display 控制显隐以保持挂载
 *     'agent' → 现有 Agent 三栏工作台（LeftPanel + ChatPanel + RightPanel）
 * 状态由 useAppShell（React Context）管理，默认 'aps'。
 */
import { useEffect, useState } from "react";
import { Layout } from "antd";
import LeftPanel from "./components/LeftPanel";
import ChatPanel from "./components/ChatPanel";
import RightPanel from "./components/RightPanel";
import { useWorkbench } from "./hooks/useWorkbench";
import { AppShellProvider, useAppShell, type AppTab } from "./hooks/useAppShell";
import SystemMenu from "./components/SystemMenu";

/** APS 入口地址：相对路径 /aps，由 vite 代理转发到 APS_PROXY_TARGET（见 vite.config.ts） */
const APS_URL = "/aps";

const TABS: { key: AppTab; label: string }[] = [
  { key: "aps", label: "排产管理平台" },
  { key: "agent", label: "AI 助手" },
];

/** 顶部左侧 Logo（横版组合图：六边形电路图标 + 清优智汇 IntelliOpt，白色线条透明底，见 public/logo-full.png） */
function Logo() {
  return (
    <img
      className="topbar-logo"
      src="/logo-full.png"
      alt="清优智汇 IntelliOpt"
      draggable={false}
    />
  );
}

function AppShell() {
  const { activeTab, setActiveTab } = useAppShell();
  const wb = useWorkbench();
  const [collapsed, setCollapsed] = useState(false);

  // 收到新的 chart 事件时自动展开右侧栏（标签切换由 useWorkbench 负责）
  const { charts } = wb;
  useEffect(() => {
    if (charts.gantt || charts.load) setCollapsed(false);
  }, [charts]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-zone topbar-left">
          <Logo />
          <span className="topbar-title">智能排产与决策支持系统</span>
        </div>

        <nav className="topbar-zone topbar-tabs" aria-label="主导航">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={`topbar-tab${activeTab === tab.key ? " active" : ""}`}
              aria-current={activeTab === tab.key ? "page" : undefined}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* 右侧：系统入口（当前角色下拉：切换角色 / 技能 / LLM 配置 / 审计日志） */}
        <div className="topbar-zone topbar-right">
          <SystemMenu wb={wb} />
        </div>
      </header>

      <main className="app-content">
        {/* 两块内容常驻挂载，仅用 display 切换：iframe 不会因切走再切回而重新加载 */}
        <div
          className="pane pane-aps"
          style={{ display: activeTab === "aps" ? "block" : "none" }}
        >
          <iframe className="aps-frame" src={APS_URL} title="APS 智能排产" />
        </div>

        <div
          className="pane pane-agent"
          style={{ display: activeTab === "agent" ? "flex" : "none" }}
        >
          <Layout className="workbench">
            <Layout.Sider width={240} theme="light" className="col-left">
              <LeftPanel wb={wb} />
            </Layout.Sider>

            <Layout.Content className="col-center">
              <ChatPanel wb={wb} />
            </Layout.Content>

            <Layout.Sider
              width={480}
              collapsedWidth={44}
              collapsible
              collapsed={collapsed}
              trigger={null}
              theme="light"
              className="col-right"
            >
              <RightPanel wb={wb} collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
            </Layout.Sider>
          </Layout>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AppShellProvider>
      <AppShell />
    </AppShellProvider>
  );
}

