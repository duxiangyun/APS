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
    const node = nodeRef.current;
    if (!node) return;
    const chart = echarts.init(node);
    chartRef.current = chart;

    const resize = () => chart.resize();
    window.addEventListener("resize", resize);

    // 容器级尺寸监听：统一壳用 display:none 切换顶部 Tab，且右栏 Sider 折叠/展开
    // 带宽度过渡动画（期间 Tabs 会重新挂载、echarts 重新 init），本组件可能在
    // 容器不可见或宽度未稳定时初始化，仅靠 window.resize 无法纠正 → 甘特图等变形。
    // 这里监听容器自身宽度，恢复到非 0 时即 resize 修正画布。
    let ro: ResizeObserver | undefined;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(() => {
        if (node.clientWidth > 0) resize();
      });
      ro.observe(node);
    }

    return () => {
      window.removeEventListener("resize", resize);
      ro?.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, true);
  }, [option]);

  return <div ref={nodeRef} style={{ width: "100%", height }} />;
}
