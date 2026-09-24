/** 中间栏：对话消息列表 + 输入框（Enter 发送，Shift+Enter 换行） */
import { useEffect, useRef, useState } from "react";
import { Button, Empty, Input, Popconfirm, Space, Tag, Tooltip, Typography } from "antd";
import { ClearOutlined, PauseCircleOutlined, SendOutlined } from "@ant-design/icons";
import type { Workbench } from "../hooks/useWorkbench";
import MessageItem from "./MessageItem";

const SAMPLE_QUESTIONS = [
  "查看涂装车间的设备负荷",
  "订单7的排产计划是怎么安排的？",
  "有哪些订单延期了？",
  "订单2为什么延期？",
];

export default function ChatPanel({ wb }: { wb: Workbench }) {
  const [text, setText] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const node = listRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [wb.items]);

  const submit = () => {
    if (!text.trim() || wb.streaming) return;
    void wb.send(text);
    setText("");
  };

  return (
    <div className="chat-panel">
      <div className="panel-header">
        <Space size={8}>
          <Typography.Text strong>对话</Typography.Text>
          <Tag bordered={false} className="session-tag">
            session {wb.sessionId}
          </Tag>
          <Tag bordered={false} color={wb.streaming ? "processing" : "default"}>
            {wb.streaming ? "生成中" : "空闲"}
          </Tag>
        </Space>
        <Popconfirm title="清空对话并新建会话？" okText="清空" cancelText="取消" onConfirm={wb.resetSession}>
          <Button size="small" type="text" icon={<ClearOutlined />}>
            清空
          </Button>
        </Popconfirm>
      </div>

      <div className="chat-messages" ref={listRef}>
        {wb.items.length === 0 && (
          <div className="empty-state">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={<span className="muted">向助手提问排产、交付与负荷问题</span>}
            />
            <div className="sample-list">
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                试试这些示例问题
              </Typography.Text>
              <div className="sample-items">
                {SAMPLE_QUESTIONS.map((q) => (
                  <Button key={q} size="small" className="sample-chip" onClick={() => void wb.send(q)}>
                    {q}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        )}
        {wb.items.map((item) => (
          <MessageItem key={item.id} item={item} />
        ))}
      </div>

      <div className="chat-input">
        <Input.TextArea
          value={text}
          autoSize={{ minRows: 1, maxRows: 4 }}
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          onChange={(e) => setText(e.target.value)}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        {wb.streaming ? (
          <Tooltip title="中止本次回复">
            <Button icon={<PauseCircleOutlined />} onClick={wb.stop}>
              停止
            </Button>
          </Tooltip>
        ) : (
          <Button type="primary" icon={<SendOutlined />} disabled={!text.trim()} onClick={submit}>
            发送
          </Button>
        )}
      </div>
    </div>
  );
}
