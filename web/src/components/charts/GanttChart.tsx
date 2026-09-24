/**
 * 甘特图（ECharts 自定义系列）
 *
 * 数据来自 SSE chart 事件（chart.type === "gantt"）：
 *   { type:"gantt", title, tasks:[{name,start,end,due,deliveries:[{period,quantity,status}]}] }
 * 每条任务渲染为一条横向区间条 + 交付量散点 + 交期虚线。
 */
import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import EChart from "../EChart";
import type { ChartPayload, GanttTask } from "../../types";

interface Props {
  chart: ChartPayload | null;
  height?: number;
}

export default function GanttChart({ chart, height = 300 }: Props) {
  const tasks: GanttTask[] = useMemo(
    () => (chart && chart.type === "gantt" ? chart.tasks : []),
    [chart],
  );

  /**
   * 归一化：单期交付（start === end）时至少占 1 个周期宽度，避免渲染成极细的条。
   * 交付点仍以散点精确标注，故不影响数据语义。
   */
  const rows = useMemo(
    () =>
      tasks.map((t, i) => {
        const start = t.start;
        const end = Math.max(t.end, t.start + 1);
        const delayed = Boolean(t.due && end > t.due);
        return {
          index: i,
          start,
          end,
          due: t.due ?? 0,
          delayed,
          label: `${start === end - 1 ? `第${start}期交付` : `${start}→${end}期`}${delayed ? " · 延期" : ""}`,
        };
      }),
    [tasks],
  );

  const option = useMemo<EChartsOption>(() => {
    const names = tasks.map((t) => t.name);
    const maxEnd = Math.max(1, ...rows.map((r) => Math.max(r.end, r.due)));

    const bars: any[] = [
      {
        type: "custom",
        name: "交付区间",
        encode: { x: [1, 2], y: 0 },
        clip: false,
        renderItem: (params: any, api: any) => {
          const idx = api.value(0);
          const start = api.coord([api.value(1), idx]);
          const end = api.coord([api.value(2), idx]);
          const band = api.size([0, 1])[1];
          const barHeight = Math.max(8, band * 0.32);
          const width = Math.max(3, end[0] - start[0]);
          const children: any[] = [
            {
              type: "rect",
              shape: { x: start[0], y: start[1] - barHeight / 2, width, height: barHeight, r: 3 },
              style: { fill: api.value(4) ? "#f97316" : "#2563eb" },
            },
            {
              type: "text",
              style: {
                text: String(api.value(3) ?? ""),
                x: start[0] + width + 6,
                y: start[1],
                fill: params.dataIndex % 2 ? "#475569" : "#64748b",
                fontSize: 11,
                textVerticalAlign: "middle",
              },
            },
          ];
          const due = Number(api.value(5));
          if (Number.isFinite(due) && due > 0) {
            const dueX = api.coord([due, idx])[0];
            children.push({
              type: "line",
              shape: { x1: dueX, y1: start[1] - band / 2, x2: dueX, y2: start[1] + band / 2 },
              style: { stroke: "#ef4444", lineDash: [3, 3], lineWidth: 1.5 },
            });
          }
          return { type: "group", children };
        },
        data: rows.map((r) => [r.index, r.start, r.end, r.label, r.delayed ? 1 : 0, r.due]),
      },
    ];

    const deliveries = tasks.flatMap((t) =>
      (t.deliveries ?? []).map((d) => [d.period, t.name, d.quantity, d.status ?? ""]),
    );
    if (deliveries.length) {
      bars.push({
        type: "scatter",
        name: "交付点",
        symbolSize: (val: any) => Math.min(22, 7 + Number(val[2] ?? 0) / 20),
        itemStyle: { color: "#10b981", borderColor: "#fff", borderWidth: 1 },
        data: deliveries,
        tooltip: {
          formatter: (p: any) =>
            `${p.value[1]}<br/>第${p.value[0]}期 交付 ${p.value[2]}${p.value[3] ? `<br/>${p.value[3]}` : ""}`,
        },
        z: 5,
      });
    }

    return {
      title: {
        text: chart?.title ?? "甘特图",
        left: 4,
        top: 0,
        textStyle: { fontSize: 13, fontWeight: 500, color: "#334155" },
      },
      grid: { left: 8, right: 30, top: 44, bottom: 4, containLabel: true },
      tooltip: { trigger: "item" },
      xAxis: {
        type: "value",
        name: "周期",
        nameGap: 6,
        min: 0,
        max: maxEnd + 1,
        minInterval: 1,
        axisLabel: { formatter: "{value}期", color: "#64748b", fontSize: 11 },
        splitLine: { lineStyle: { color: "#eef2f7" } },
      },
      yAxis: {
        type: "category",
        data: names,
        inverse: true,
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: { color: "#334155", fontSize: 12, width: 120, overflow: "truncate" },
      },
      series: bars,
    };
  }, [chart, rows, tasks]);

  return <EChart option={option} height={height} />;
}
