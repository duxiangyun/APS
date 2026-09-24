/** 单条消息：Markdown 渲染 + 工具调用折叠卡片 */
import { Alert, Spin } from "antd";
import ReactMarkdown from "react-markdown";
import type { ChatItem } from "../types";
import ToolCallCard from "./ToolCallCard";

export default function MessageItem({ item }: { item: ChatItem }) {
  const isUser = item.kind === "user";
  return (
    <div className={`msg ${item.kind}`}>
      <div className={`bubble ${item.kind}`}>
        {item.tools.length > 0 && (
          <div className="tool-list">
            {item.tools.map((call) => (
              <ToolCallCard key={call.id} call={call} />
            ))}
          </div>
        )}

        {item.content ? (
          isUser ? (
            <div className="plain-text">{item.content}</div>
          ) : (
            <div className="markdown">
              <ReactMarkdown>{item.content}</ReactMarkdown>
            </div>
          )
        ) : null}

        {item.streaming && !item.content && item.tools.length === 0 && (
          <div className="thinking">
            <Spin size="small" /> <span className="muted">正在思考…</span>
          </div>
        )}

        {item.error && (
          <Alert type="warning" showIcon message={item.error} style={{ marginTop: 8 }} />
        )}
      </div>
    </div>
  );
}
