/**
 * 右侧栏（480px，可折叠）：甘特图 / 设备负荷 / KPI
 * 收到 SSE chart 事件时自动切换到对应标签页并渲染。
 * 支持「固定当前图表」：钉选后同类图表事件不再刷新该视图。
 */
import { Button, Tabs, Tag, Tooltip, Typography } from "antd";
import {
  LockOutlined,
  BarChartOutlined,
  ScheduleOutlined,
  DashboardOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from "@ant-design/icons";
import GanttChart from "./charts/GanttChart";
import LoadChart from "./charts/LoadChart";
import KpiChart from "./charts/KpiChart";
import type { Workbench } from "../hooks/useWorkbench";
import { placeholderGantt, placeholderLoad } from "../utils/chart";
import type { ChartSlot } from "../types";

const TAB_META: Record<ChartSlot, { icon: React.ReactNode; label: string }> = {
  gantt: { icon: <ScheduleOutlined />, label: "甘特图" },
  load:  { icon: <BarChartOutlined />, label: "设备负荷" },
  kpi:   { icon: <DashboardOutlined />, label: "KPI" },
};

interface Props {
  wb: Workbench;
  collapsed: boolean;
  onToggle: () => void;
}

function ChartFootnote({ source, name, pinned }: { source: "event" | "placeholder"; name?: string; pinned?: boolean }) {
  return (
    <div className="chart-footnote">
      {pinned ? (
        <Tag color="gold" bordered={false} icon={<LockOutlined />}>已固定</Tag>
      ) : (
        <>
          {source === "event" ? (
            <Tag color="blue" bordered={false}>来自 chart 事件</Tag>
          ) : (
            <Tag bordered={false}>占位数据（等待 chart 事件）</Tag>
          )}
          {name && <span className="muted">工具 {name}</span>}
        </>
      )}
    </div>
  );
}

export default function RightPanel({ wb, collapsed, onToggle }: Props) {
  const { charts, activeTab, setActiveTab, pinnedSlot, pinSlot } = wb;
  const gantt = charts.gantt ?? placeholderGantt();
  const load  = charts.load  ?? placeholderLoad();
  const kpi   = charts.kpi && charts.kpi.type === "kpi" ? charts.kpi : null;
  const ganttSrc = charts.gantt ? "event" : "placeholder";
  const loadSrc  = charts.load  ? "event" : "placeholder";
  const kpiSrc   = charts.kpi   ? "event" : "placeholder";

  function makePane(slot: ChartSlot) {
    const src = slot === "gantt" ? ganttSrc : slot === "load" ? loadSrc : kpiSrc;
    const name = slot === "gantt" ? "get_schedule / explain_delay"
      : slot === "load" ? "get_machine_load / get_bottleneck" : "get_kpi";
    const pinned = pinnedSlot === slot;
    return (
      <div className="tab-body">
        {slot === "kpi" ? (
          <KpiChart chart={kpi} height={300} />
        ) : slot === "gantt" ? (
          <GanttChart chart={gantt} height={300} />
        ) : (
          <LoadChart chart={load} height={300} />
        )}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
          <ChartFootnote source={src} name={name} pinned={pinned} />
          {!pinned && (
            <Button size="small" type="link" icon={<LockOutlined />} onClick={() => pinSlot(slot)}>
              固定图表
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="right-panel">
      <div className="panel-header">
        <Typography.Text strong>分析视图</Typography.Text>
        <Tooltip title={collapsed ? "展开右侧栏" : "折叠右侧栏"}>
          <Button
            size="small"
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={onToggle}
          />
        </Tooltip>
      </div>
      {!collapsed && (
        <Tabs
          className="right-tabs"
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as ChartSlot)}
          items={[
            {
              key: "gantt",
              label: (
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  {TAB_META.gantt.icon}
                  {TAB_META.gantt.label}
                  {pinnedSlot === "gantt" && <LockOutlined style={{ color: "#f59e0b", fontSize: 12 }} />}
                </span>
              ),
              children: makePane("gantt"),
            },
            {
              key: "load",
              label: (
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  {TAB_META.load.icon}
                  {TAB_META.load.label}
                  {pinnedSlot === "load" && <LockOutlined style={{ color: "#f59e0b", fontSize: 12 }} />}
                </span>
              ),
              children: makePane("load"),
            },
            {
              key: "kpi",
              label: (
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  {TAB_META.kpi.icon}
                  {TAB_META.kpi.label}
                  {pinnedSlot === "kpi" && <LockOutlined style={{ color: "#f59e0b", fontSize: 12 }} />}
                </span>
              ),
              children: makePane("kpi"),
            },
          ]}
        />
      )}
    </div>
  );
}
