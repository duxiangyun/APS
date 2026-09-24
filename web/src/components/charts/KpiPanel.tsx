/**
 * KPI 面板：核心指标 + 按优先级交付达成
 * 数据经 agent 透传读取 APS /open/kpi/*（前端不直连 APS）
 */
import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Empty, Space, Spin, Table, Tag } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { agentApi, fmtNumber } from "../../api";
import type { DeliveryInfo, DeliveryRow, KpiSummary } from "../../types";

const KPI_LABELS: Record<string, string> = {
  sales_revenue: "销售收入",
  manufacturing_cost: "制造成本",
  purchase_cost: "采购成本",
  outsource_cost: "外协成本",
  inventory_cost: "库存成本",
  delay_penalty: "延期罚金",
  fixture_cost: "工装成本",
  infeasible_cost: "不可行成本",
  profit: "利润",
};

/** 需要隐藏的字段（非金额类） */
const HIDDEN = new Set(["run_id"]);

export default function KpiPanel() {
  const [kpi, setKpi] = useState<KpiSummary | null>(null);
  const [delivery, setDelivery] = useState<DeliveryInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [summary, info] = await Promise.all([
        agentApi.aps.kpiSummary(),
        agentApi.aps.kpiDelivery(),
      ]);
      setKpi(summary);
      setDelivery(info);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const entries = Object.entries(kpi?.kpi ?? {}).filter(([k, v]) => !HIDDEN.has(k) && v !== null);

  return (
    <div className="kpi-panel">
      <Space style={{ marginBottom: 12 }}>
        <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={load}>
          刷新
        </Button>
        {kpi?.run && (
          <span className="muted">
            run_id={String(kpi.run.run_id ?? "-")} · {String(kpi.run.run_time ?? "")}
          </span>
        )}
      </Space>

      {error && <Alert type="warning" showIcon message={error} style={{ marginBottom: 12 }} />}
      {loading && !kpi && <Spin size="small" />}

      {kpi && (
        <div className="kpi-grid">
          {entries.map(([key, value]) => (
            <div key={key} className="kpi-item">
              <div className="label">{KPI_LABELS[key] ?? key}</div>
              <div className={`value${key === "profit" ? " highlight" : ""}`}>{fmtNumber(value)}</div>
            </div>
          ))}
        </div>
      )}

      {delivery && (
        <>
          <div className="section-title">
            准交率 <Tag color="blue">{delivery.ontime_rate ?? "-"}%</Tag>
          </div>
          <Table<DeliveryRow>
            size="small"
            rowKey="priority_level"
            pagination={false}
            dataSource={delivery.by_priority ?? []}
            columns={[
              { title: "优先级", dataIndex: "priority_level", width: 68 },
              { title: "订单", dataIndex: "order_count_total", width: 56 },
              { title: "按期", dataIndex: "order_count_ontime", width: 56 },
              { title: "延期", dataIndex: "order_count_delayed", width: 56 },
              { title: "未交付", dataIndex: "order_count_undelivered", width: 68 },
            ]}
          />
        </>
      )}

      {!loading && !kpi && !error && <Empty description="暂无 KPI 数据（需先在 APS 中完成求解）" />}
    </div>
  );
}
