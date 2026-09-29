/** 单条消息：Markdown 渲染 + 工具调用折叠卡片 */
import { Alert, Spin } from "antd";
import ReactMarkdown from "react-markdown";
// GFM 扩展：表格 / 删除线 / 自动链接 / 任务列表。
// react-markdown 默认仅 CommonMark，缺此插件时 `| a | b |` 会被当作普通段落文本，
// 表现为所有竖线挤在一行。
import remarkGfm from "remark-gfm";
import type { ChatItem } from "../types";
import ToolCallCard from "./ToolCallCard";

/** 渲染选项：GFM 表格等扩展在此统一开启 */
const REMARK_PLUGINS = [remarkGfm];

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
              <ReactMarkdown remarkPlugins={REMARK_PLUGINS}>{item.content}</ReactMarkdown>
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
