/**
 * 图表数据转换工具
 *
 * - chartFromToolResult：把 tool_result 的原始数据兜底转换为 chart 事件同样的结构
 *   （正常情况下图表由后端 chart 事件驱动；这里仅在未收到 chart 事件时保证面板不空）
 * - 占位数据：后端暂无数据时先渲染占位甘特图/负荷图
 */
import type { ChartPayload, GanttDelivery, GanttTask } from "../types";

interface ScheduleLike {
  order?: { order_id?: number; product_code?: string; due_period?: number | null };
  deliveries?: { period?: number | null; quantity?: number | null; status?: string }[];
}

/** 由 get_schedule 工具结果构造甘特图数据 */
export function ganttFromToolResult(name: string, data?: Record<string, unknown>): ChartPayload | null {
  if (name !== "get_schedule" || !data) return null;
  const schedule = data as ScheduleLike;
  const order = schedule.order ?? {};
  const deliveries: GanttDelivery[] = (schedule.deliveries ?? []).map((d) => ({
    period: Number(d.period ?? 0),
    quantity: Number(d.quantity ?? 0),
    status: d.status,
  }));
  if (!deliveries.length) return null;
  const lastPeriod = Math.max(...deliveries.map((d) => d.period));
  const due = order.due_period ?? null;
  const end = Math.max(lastPeriod, due ?? 0);
  const task: GanttTask = {
    name: `订单${order.order_id ?? ""} ${order.product_code ?? ""}`.trim(),
    start: 1,
    end,
    due,
    deliveries,
  };
  return {
    type: "gantt",
    title: `订单${order.order_id ?? ""} 交付甘特图（周期）`,
    tasks: [task],
    periods: Array.from({ length: end }, (_, i) => i + 1),
  };
}

/** 由 get_machine_load 工具结果构造负荷图数据（后端已带 chart，此处为兜底） */
export function loadFromToolResult(name: string, data?: Record<string, unknown>): ChartPayload | null {
  if (name !== "get_machine_load" || !data) return null;
  const matrix = (data.matrix ?? data.resources ?? []) as Record<string, unknown>[];
  if (!matrix.length) return null;

  const periodSet = new Set<number>();
  for (const r of matrix) {
    for (const k of Object.keys(r)) {
      const m = /^period_(\d+)$/.exec(k);
      if (m) periodSet.add(Number(m[1]));
    }
  }
  const periods = [...periodSet].sort((a, b) => a - b);

  const resources = matrix.map((r) => {
    const series: Record<string, number> = {};
    for (const p of periods) series[String(p)] = Number(r[`period_${p}`] ?? 0);
    return {
      resource_code: String(r.resource_code ?? r.code ?? "-"),
      capacity: Number(r.capacity ?? 0),
      peak_rate: Number(r.peak_rate ?? 0),
      avg_rate: Number(r.avg_rate ?? 0),
      total_load: Number(r.total_load ?? r.total ?? 0),
      normal_cost: Number(r.normal_cost ?? 0),
      periods: series,
    };
  });

  return { type: "load", title: "设备负荷", periods, resources };
}

/** 占位甘特图数据（未收到任何 chart 事件时展示） */
export function placeholderGantt(): ChartPayload {
  const mk = (name: string, start: number, end: number, due: number, qty: number[]): GanttTask => ({
    name,
    start,
    end,
    due,
    deliveries: qty.map((q, i) => ({ period: start + i, quantity: q, status: "占位数据" })),
  });
  return {
    type: "gantt",
    title: "甘特图占位（等待 chart 事件）",
    periods: [1, 2, 3, 4, 5, 6],
    tasks: [
      mk("订单-示例A MN-TM3G2A4", 1, 5, 5, [10, 15, 20, 0, 0]),
      mk("订单-示例B MN-TM3G2A5", 1, 4, 3, [8, 12, 0, 14]),
      mk("订单-示例C MN-TM3G2A6", 2, 6, 6, [0, 6, 9, 9, 6]),
    ],
  };
}

/** 占位负荷图数据 */
export function placeholderLoad(): ChartPayload {
  const codes = ["涂装-1", "装配-1", "机加-1", "检测-1", "包装-1"];
  const totals = [540, 470, 380, 260, 180];
  const periods = [1, 2, 3, 4];
  return {
    type: "load",
    title: "设备负荷占位（等待 chart 事件）",
    periods,
    resources: codes.map((code, i) => ({
      resource_code: code,
      capacity: 480,
      peak_rate: Math.round((totals[i] / 4 / 480) * 100),
      avg_rate: Math.round((totals[i] / 4 / 480) * 100),
      total_load: totals[i],
      normal_cost: 0,
      periods: Object.fromEntries(periods.map((p) => [String(p), Math.round(totals[i] / 4)])),
    })),
  };
}
