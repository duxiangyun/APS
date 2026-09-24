/** ECharts 轻量封装（避免引入额外依赖，统一 resize/dispose 生命周期） */
import { useEffect, useRef } from "react";
import type { EChartsOption } from "echarts";
import echarts from "../utils/echarts";

interface Props {
  option: EChartsOption;
  height?: number | string;
}

export default function EChart({ option, height = 320 }: Props) {
  const nodeRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!nodeRef.current) return;
    const chart = echarts.init(nodeRef.current);
    chartRef.current = chart;
    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, true);
  }, [option]);

  return <div ref={nodeRef} style={{ width: "100%", height }} />;
}
