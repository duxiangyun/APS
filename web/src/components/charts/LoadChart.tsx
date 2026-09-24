/**
 * 设备负荷图（ECharts）
 *
 * 数据来自 SSE chart 事件（chart.type === "load"）：
 *   chart.resources 每行形如 {resource_code, capacity, peak_rate, avg_rate, total_load, periods:{"1":..}}
 *
 * 渲染策略：
 *   - 行内含 period_N 明细 → 按周期堆积柱 + 单期产能线（同一量纲，可直接比较是否超载）
 *   - 仅含累计负荷 → 累计负荷柱 + 单期产能线
 */
import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import EChart from "../EChart";
import type { ChartPayload } from "../../types";

interface Props {
  chart: ChartPayload | null;
  height?: number;
}

interface Row {
  code: string;
  total: number;
  capacity: number | null;
  periods: Record<number, number>;
}

const PALETTE = [
  "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd", "#0ea5e9", "#38bdf8",
  "#7dd3fc", "#6366f1", "#818cf8", "#a5b4fc", "#0891b2", "#22d3ee",
];

export default function LoadChart({ chart, height = 300 }: Props) {
  const { rows, periodKeys } = useMemo(() => {
    const resources = chart && chart.type === "load" ? chart.resources : [];
    const keys = new Set<number>();
    for (const r of resources) {
      for (const k of Object.keys(r.periods ?? {})) {
        const p = Number(k);
        if (Number.isFinite(p)) keys.add(p);
      }
    }

    const parsed: Row[] = resources.map((r) => {
      const periods: Record<number, number> = {};
      for (const [k, v] of Object.entries(r.periods ?? {})) {
        const p = Number(k);
        if (Number.isFinite(p)) periods[p] = Number(v ?? 0);
      }
      return {
        code: r.resource_code,
        total: Number(r.total_load ?? 0),
        capacity: r.capacity === undefined || r.capacity === null ? null : Number(r.capacity),
        periods,
      };
    });

    parsed.sort((a, b) => b.total - a.total);
    return { rows: parsed.slice(0, 12), periodKeys: [...keys].sort((a, b) => a - b) };
  }, [chart]);

  const option = useMemo<EChartsOption>(() => {
    const codes = rows.map((r) => r.code);
    const stacked = periodKeys.length > 0;

    const series: any[] = stacked
      ? periodKeys.map((p, i) => ({
          name: `第${p}期`,
          type: "bar",
          stack: "load",
          barMaxWidth: 26,
          itemStyle: { color: PALETTE[i % PALETTE.length] },
          data: rows.map((r) => r.periods[p] ?? 0),
        }))
      : [
          {
            name: "累计负荷",
            type: "bar",
            barMaxWidth: 26,
            itemStyle: { color: "#3b82f6", borderRadius: [3, 3, 0, 0] },
            data: rows.map((r) => r.total),
          },
        ];

    series.push({
      name: "单期产能",
      type: "line",
      symbol: "none",
      lineStyle: { type: "dashed", color: "#ef4444", width: 1.5 },
      data: rows.map((r) => r.capacity),
    });

    return {
      title: {
        text: chart?.title ?? "设备负荷",
        left: 4,
        top: 0,
        textStyle: { fontSize: 13, fontWeight: 500, color: "#334155" },
      },
      grid: { left: 8, right: 16, top: 52, bottom: 4, containLabel: true },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: {
        type: "scroll",
        top: 22,
        right: 4,
        itemWidth: 10,
        itemHeight: 8,
        textStyle: { fontSize: 11 },
        data: series.map((s) => s.name),
      },
      xAxis: {
        type: "category",
        data: codes,
        axisLabel: { rotate: 35, color: "#64748b", fontSize: 11 },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "#e2e8f0" } },
      },
      yAxis: {
        type: "value",
        name: stacked ? "单期负荷" : "累计负荷",
        nameTextStyle: { fontSize: 11, color: "#94a3b8" },
        axisLabel: { color: "#64748b", fontSize: 11 },
        splitLine: { lineStyle: { color: "#eef2f7" } },
      },
      series,
    };
  }, [chart, periodKeys, rows]);

  return <EChart option={option} height={height} />;
}
