/** 工具调用折叠卡片：工具名 + 参数 + 结果摘要（+ 原始数据） */
import { Collapse, Tag } from "antd";
import type { ToolCall } from "../types";

const STATUS_META: Record<ToolCall["status"], { text: string; color: string }> = {
  running: { text: "执行中", color: "processing" },
  ok: { text: "成功", color: "success" },
  error: { text: "失败", color: "error" },
};

function inlineArgs(args: Record<string, unknown>): string {
  const entries = Object.entries(args ?? {}).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (!entries.length) return "无参数";
  return entries
    .slice(0, 3)
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" · ");
}

export default function ToolCallCard({ call }: { call: ToolCall }) {
  const meta = STATUS_META[call.status];
  const argsText = JSON.stringify(call.args ?? {}, null, 2);
  const dataText = call.data ? JSON.stringify(call.data, null, 2) : "";

  const label = (
    <div className="tool-label">
      <Tag color={meta.color} style={{ marginInlineEnd: 8 }}>
        {meta.text}
      </Tag>
      <span className="tool-name">{call.name}</span>
      <span className="tool-inline-args">{inlineArgs(call.args)}</span>
      {call.durationMs !== undefined && <span className="tool-duration">{call.durationMs} ms</span>}
    </div>
  );

  const children = (
    <div className="tool-body">
      <div className="tool-section-title">参数</div>
      <pre className="tool-pre">{argsText}</pre>
      {call.summary && (
        <>
          <div className="tool-section-title">结果摘要</div>
          <div className="tool-summary">{call.summary}</div>
        </>
      )}
      {dataText && (
        <Collapse
          size="small"
          ghost
          items={[
            {
              key: "raw",
              label: <span className="tool-section-title">原始数据</span>,
              children: <pre className="tool-pre">{dataText}</pre>,
            },
          ]}
        />
      )}
    </div>
  );

  return (
    <Collapse
      size="small"
      ghost
      className="tool-call"
      defaultActiveKey={call.status === "error" ? [call.id] : []}
      items={[{ key: call.id, label, children }]}
    />
  );
}
