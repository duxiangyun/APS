/**
 * KPI 图表组件：接收 agent chart 事件中的 kpi 数据并渲染 Ant Design 卡片
 *
 * 数据结构（SSE chart 事件，chart.type === "kpi"）：
 *   { type:"kpi", title, items:[{key,label,value,unit,hint,emphasize,color}],
 *     delivery_by_priority:[{priority_level,order_count_*...}],
 *     run_id, profit_margin }
 *
 *  fallback：若未收到 chart 事件，展示占位 KPI 面板（从 agent API 直读）
 */
import { Statistic, Table, Tag, Typography } from "antd";
import type { DeliveryRow, KpiChartPayload } from "../../types";
import { fmtNumber } from "../../api";

const PROFIT_COLOR = "#22c55e";
const BLUE_COLOR = "#2563eb";
const RED_COLOR = "#ef4444";

function colorFor(key: string, emphasize: boolean, color?: string): string {
  if (color) return color;
  if (key === "profit" || key === "ontime_rate") return emphasize ? PROFIT_COLOR : BLUE_COLOR;
  if (key === "delay_penalty") return RED_COLOR;
  return "#1e293b";
}

function formatValue(item: { value: number; unit: string }) {
  const { value, unit } = item;
  if (unit === "%") return `${value.toFixed(1)}%`;
  if (Math.abs(value) >= 10000) return `${fmtNumber(value, 0)} 万`;
  return `${fmtNumber(value, 0)} ${unit}`;
}

interface Props {
  chart: KpiChartPayload | null;
  height?: number;
}

export default function KpiChart({ chart }: Props) {
  const title = chart?.title ?? "KPI 概览";
  const items = chart?.items ?? [];
  const delivery = chart?.delivery_by_priority ?? [];
  const runId = chart?.run_id;

  const profitMargin = chart?.profit_margin;

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Typography.Text strong style={{ fontSize: 13 }}>{title}</Typography.Text>
        {runId !== undefined && runId !== null && (
          <Tag bordered={false} style={{ marginLeft: 8 }}>run_id={runId}</Tag>
        )}
      </div>

      {items.length > 0 ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 8 }}>
          {items.map((item) => (
            <Statistic
              key={item.key}
              title={item.label}
              value={item.value}
              precision={item.unit === "%" ? 1 : 0}
              suffix={item.unit === "%" ? "%" : ""}
              valueStyle={{
                color: colorFor(item.key, Boolean(item.emphasize), item.color),
                fontWeight: item.emphasize ? 700 : 500,
              }}
              formatter={() => formatValue(item)}
            />
          ))}
        </div>
      ) : (
        <div style={{ padding: 16, color: "#94a3b8", fontSize: 13, textAlign: "center" }}>
          暂无 KPI 数据（需先在 APS 中完成求解）
        </div>
      )}

      {delivery.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            按优先级交付达成
          </Typography.Text>
          <Table<DeliveryRow>
            size="small"
            rowKey="priority_level"
            pagination={false}
            dataSource={delivery}
            style={{ marginTop: 6 }}
            columns={[
              { title: "优先级", dataIndex: "priority_level", width: 60, align: "center" },
              { title: "订单数", dataIndex: "order_count_total", width: 60, align: "center" },
              {
                title: "按期",
                dataIndex: "order_count_ontime",
                width: 60,
                align: "center",
                render: (v: number) => v > 0 ? <Tag color="green">{v}</Tag> : v,
              },
              {
                title: "延期",
                dataIndex: "order_count_delayed",
                width: 60,
                align: "center",
                render: (v: number) => v > 0 ? <Tag color="red">{v}</Tag> : v,
              },
              {
                title: "部分",
                dataIndex: "order_count_partial",
                width: 60,
                align: "center",
                render: (v: number) => v > 0 ? <Tag color="orange">{v}</Tag> : v,
              },
            ]}
          />
        </div>
      )}

      {profitMargin !== undefined && (
        <div style={{ marginTop: 8, padding: "6px 10px", background: "#f0fdf4", borderRadius: 6, fontSize: 12, color: "#166534", display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontWeight: 600 }}>毛利率</span>
          <span>{profitMargin.toFixed(1)}%</span>
          <span style={{ color: "#555" }}>·</span>
          <span>利润 {fmtNumber(chart?.items.find((i) => i.key === "profit")?.value, 0)} 元</span>
        </div>
      )}
    </div>
  );
}