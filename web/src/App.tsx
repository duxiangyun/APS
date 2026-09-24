/**
 * WorkBuddy 风格三栏工作台
 *   左 240px：角色 / 技能 / 连接状态与设置
 *   中 自适应：对话 + 工具卡片 + 输入
 *   右 480px：甘特图 / 设备负荷 / KPI（可折叠）
 */
import { useEffect, useState } from "react";
import { Layout } from "antd";
import LeftPanel from "./components/LeftPanel";
import ChatPanel from "./components/ChatPanel";
import RightPanel from "./components/RightPanel";
import { useWorkbench } from "./hooks/useWorkbench";

export default function App() {
  const wb = useWorkbench();
  const [collapsed, setCollapsed] = useState(false);

  // 收到新的 chart 事件时自动展开右侧栏（标签切换由 useWorkbench 负责）
  const { charts } = wb;
  useEffect(() => {
    if (charts.gantt || charts.load) setCollapsed(false);
  }, [charts]);

  return (
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
  );
}
