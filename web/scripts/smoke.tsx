/**
 * 前端冒烟自检（无浏览器环境）
 *
 *   npm run smoke
 *
 * 1) 三栏工作台整体 SSR 渲染（角色/技能/标签页等关键元素存在）
 * 2) 甘特图 / 负荷图在「chart 事件数据」「占位数据」「空数据」三种输入下均可渲染
 * 3) 真实 SSE 闭环：请求 agent /chat/stream，用前端同一套解析与归约逻辑
 *    验证 token 累加、工具卡片状态、图表更新
 */
import { renderToString } from "react-dom/server";

// --- 极简浏览器环境垫片（仅满足组件在 node 下渲染） ---
const store: Record<string, string> = {};
(globalThis as unknown as { window: unknown }).window = {
  localStorage: {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => { store[k] = v; },
  },
  setInterval: () => 0,
  clearInterval: () => undefined,
  addEventListener: () => undefined,
  removeEventListener: () => undefined,
};
(globalThis as unknown as { document: unknown }).document = { getElementById: () => null };

import App from "../src/App";
import GanttChart from "../src/components/charts/GanttChart";
import LoadChart from "../src/components/charts/LoadChart";
import { ganttFromToolResult, placeholderGantt, placeholderLoad } from "../src/utils/chart";
import { parseSseBuffer, reduceEvent } from "../src/utils/events";
import type { ChatItem } from "../src/types";

const AGENT = process.env.AGENT_BASE_URL || "http://127.0.0.1:8100";
let failed = 0;
function check(name: string, ok: boolean, extra = "") {
  if (!ok) failed += 1;
  console.log(`${ok ? "OK  " : "FAIL"} ${name}${extra ? ` · ${extra}` : ""}`);
}

// ---------------------------------------------------------------- 1. 渲染
console.log("\n== 1. 三栏工作台渲染 ==");
const html = renderToString(<App />);
check("App 渲染", html.length > 1000, `${html.length} 字符`);
for (const key of [
  "APS WorkBuddy",            // 品牌
  "当前角色", "计划员", "主管", "经理",  // 角色切换
  "技能",                      // 技能列表
  "Agent 后端", "APS 数据", "LLM", "设置", // 底部状态 + 设置入口
  "甘特图", "设备负荷", "KPI",  // 右侧标签页
  "输入问题", "发送",           // 输入区
]) {
  check(`包含「${key}」`, html.includes(key));
}

// ---------------------------------------------------------------- 2. 图表
console.log("\n== 2. 图表渲染 ==");
check("占位甘特图", renderToString(<GanttChart chart={placeholderGantt()} />).length > 0);
check("占位负荷图", renderToString(<LoadChart chart={placeholderLoad()} />).length > 0);
check("空数据不崩溃", renderToString(<GanttChart chart={null} />).length > 0
  && renderToString(<LoadChart chart={null} />).length > 0);
check("工具结果 → 甘特图兜底", Boolean(ganttFromToolResult("get_schedule", {
  order: { order_id: 7, due_period: 5 },
  deliveries: [{ period: 5, quantity: 45 }],
})));

// ---------------------------------------------------------------- 3. SSE 闭环
console.log("\n== 3. SSE 闭环（真实 agent 数据） ==");
const cases: { question: string; skills: string[]; expectTool: string; expectChart: "gantt" | "load"; chartOptional?: boolean }[] = [
  { question: "订单7的排产计划是怎么安排的？", skills: [], expectTool: "get_schedule", expectChart: "gantt" },
  { question: "查看涂装车间的设备负荷", skills: [], expectTool: "get_machine_load", expectChart: "load" },
  { question: "有哪些订单延期了？", skills: [], expectTool: "get_orders", expectChart: "gantt", chartOptional: true },
  { question: "订单2为什么延期？", skills: [], expectTool: "explain_delay", expectChart: "gantt" },
];

async function runCase(c: typeof cases[number]) {
  const resp = await fetch(`${AGENT}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: c.question, role: "planner", session_id: "smoke", skills: c.skills }),
  });
  if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`);

  // 用与浏览器完全相同的解析与归约逻辑
  let item: ChatItem = { id: "bot", kind: "assistant", content: "", tools: [], streaming: true };
  const startedAt = new Map<string, number>();
  const charts: Record<string, string> = {};
  const eventTypes: string[] = [];
  const payloads: { type: string; chart: unknown }[] = [];

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSseBuffer(buffer);
    buffer = rest;
    for (const ev of events) {
      eventTypes.push(String(ev.type));
      const out = reduceEvent(item, ev, startedAt);
      item = out.item;
      if (out.chart) {
        const slot = out.chart.type === "gantt" ? "gantt" : "load";
        charts[slot] = out.chart.type;
        payloads.push({ type: out.chart.type, chart: out.chart });
      }
    }
  }

  // 用真实 chart 载荷渲染图表，验证前端可视化不炸
  for (const p of payloads) {
    const htmlOut = p.type === "gantt"
      ? renderToString(<GanttChart chart={p.chart as never} height={240} />)
      : renderToString(<LoadChart chart={p.chart as never} height={240} />);
    check(`${c.expectTool} → 真实 chart 载荷渲染`, htmlOut.length > 0, `${p.type}`);
  }

  const tool = item.tools.find((t) => t.name === c.expectTool);
  check(`${c.question} → ${c.expectTool} 卡片`, Boolean(tool) && tool?.status === "ok",
    tool?.summary?.slice(0, 40) ?? "");
  check(`${c.question} → 文本回复`, item.content.length > 10, `${item.content.length} 字`);
  // 图表断言：get_orders 后端不产 chart、前端兜底仅支持 get_schedule，
  // 是否出图取决于 LLM 是否追加调用产图工具 → chartOptional 时未触发不算失败（触发则必须类型正确）
  const gotChartTypes = Object.keys(charts).map((k) => charts[k]);
  check(`${c.question} → 图表 ${c.expectChart}`,
    (c.chartOptional && gotChartTypes.length === 0)
      || charts[c.expectChart] === c.expectChart,
    gotChartTypes.length ? gotChartTypes.join(",") : "未触发（可选）");
  check(`${c.question} → 事件序列`, eventTypes.includes("tool_call")
    && eventTypes.includes("tool_result") && eventTypes.includes("token")
    && eventTypes.includes("done"), eventTypes.join(">"));
}

async function main() {
  for (const c of cases) {
    try {
      await runCase(c);
    } catch (e) {
      check(`${c.question}`, false, (e as Error).message);
    }
  }

  console.log(`\n${failed === 0 ? "✅ 全部通过" : `❌ ${failed} 项失败`}`);
  process.exit(failed === 0 ? 0 : 1);
}

void main();
