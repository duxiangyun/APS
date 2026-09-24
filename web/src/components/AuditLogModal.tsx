/**
 * 审计日志弹窗（仅 admin 角色可见入口）：
 * 展示 SQLite audit_log 表最近记录，支持按角色 / 工具过滤与刷新
 */
import { useCallback, useEffect, useState } from "react";
import { Empty, Modal, Select, Space, Table, Tag, Tooltip, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { ReloadOutlined } from "@ant-design/icons";
import { agentApi } from "../api";
import type { AuditLogEntry, Skill } from "../types";

const TOOL_OPTIONS = ["get_orders", "get_schedule", "get_machine_load",
  "get_bottleneck", "explain_delay", "get_kpi",
  "get_audit_logs", "get_system_status"];
const ROLE_OPTIONS = ["planner", "supervisor", "manager", "analyst",
  "purchaser", "admin", "default"];

export default function AuditLogModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [role, setRole] = useState<string | undefined>();
  const [tool, setTool] = useState<string | undefined>();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { logs: list } = await agentApi.audit.logs({ role, tool, limit: 100 });
      setLogs(list);
    } catch (e) {
      message.error(`加载审计日志失败：${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [role, tool]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  const columns: ColumnsType<AuditLogEntry> = [
    {
      title: "时间", dataIndex: "created_at", width: 150,
      render: (v: string) => <Typography.Text style={{ fontSize: 12 }}>{v}</Typography.Text>,
    },
    {
      title: "角色", dataIndex: "role", width: 90,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: "工具", dataIndex: "tool_name", width: 150,
      render: (v: string) => <code style={{ fontSize: 12 }}>{v}</code>,
    },
    {
      title: "状态", dataIndex: "status", width: 80,
      render: (v: string) =>
        v === "success" ? <Tag color="green">成功</Tag> : <Tag color="red">失败</Tag>,
    },
    {
      title: "缓存", dataIndex: "cache_hit", width: 70,
      render: (v: boolean) =>
        v ? <Tag color="cyan">命中</Tag> : <Tag>未命中</Tag>,
    },
    {
      title: "耗时", dataIndex: "duration_ms", width: 80,
      render: (v: number) => <span style={{ fontSize: 12 }}>{Math.round(v)}ms</span>,
    },
    {
      title: "结果摘要", dataIndex: "result_summary", ellipsis: true,
      render: (v: string, row) => (
        <Tooltip title={<pre className="tooltip-pre">{JSON.stringify(row.params, null, 2)}</pre>}>
          <Typography.Text style={{ fontSize: 12 }} ellipsis={{ rows: 2 }}>{v}</Typography.Text>
        </Tooltip>
      ),
    },
    {
      title: "会话", dataIndex: "session_id", width: 110,
      render: (v: string) => <span style={{ fontSize: 11, color: "#999" }}>{v}</span>,
    },
  ];

  return (
    <Modal
      title="审计日志（工具调用记录）"
      open={open}
      onCancel={onClose}
      footer={null}
      width={920}
      destroyOnClose
    >
      <Space style={{ marginBottom: 12 }}>
        <Select
          allowClear placeholder="全部角色" style={{ width: 140 }} value={role}
          onChange={(v) => setRole(v)}
          options={ROLE_OPTIONS.map((r) => ({ value: r, label: r }))}
        />
        <Select
          allowClear placeholder="全部工具" style={{ width: 180 }} value={tool}
          onChange={(v) => setTool(v)}
          options={TOOL_OPTIONS.map((t) => ({ value: t, label: t }))}
        />
        <a onClick={() => void load()} style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <ReloadOutlined /> 刷新
        </a>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          共 {logs.length} 条（最近优先，最多 100）
        </Typography.Text>
      </Space>
      <Table<AuditLogEntry>
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={logs}
        pagination={{ pageSize: 15, showSizeChanger: false }}
        locale={{ emptyText: <Empty description="暂无记录（进行一次对话或工具调用后刷新）" /> }}
        scroll={{ y: 420 }}
      />
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        来源：agent/data/audit.db 的 audit_log 表（JSONL 文件同步保留为备份）。
        confirmed 列预留：写入型工具需用户二次确认后才执行。
      </Typography.Text>
    </Modal>
  );
}

// 保留导入引用（Skill 类型供后续扩展使用）
export type { Skill };
