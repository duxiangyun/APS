/**
 * 审计日志弹窗（全屏）：
 * - 表格列：时间 / 角色 / 工具 / 状态 / 耗时 / cache_hit / 摘要 / 会话
 * - 过滤：按角色、按工具、按状态
 * - 数据权限：admin 看全部；其他角色固定只看自己的记录（role 过滤锁定）
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Empty, Modal, Select, Space, Table, Tag, Tooltip, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { ReloadOutlined } from "@ant-design/icons";
import { agentApi } from "../api";
import type { AuditLogEntry, RoleKey, Skill } from "../types";

const TOOL_OPTIONS = ["get_orders", "get_schedule", "get_machine_load",
  "get_bottleneck", "explain_delay", "get_kpi",
  "get_audit_logs", "get_system_status"];
const ROLE_OPTIONS = ["planner", "supervisor", "manager", "analyst",
  "purchaser", "admin", "default"];
const STATUS_OPTIONS = [
  { value: "success", label: "成功" },
  { value: "failed", label: "失败" },
];

export default function AuditLogModal({
  open,
  onClose,
  currentRole,
}: {
  open: boolean;
  onClose: () => void;
  /** 当前登录角色：admin 看全部，其他角色只看自己的记录 */
  currentRole?: RoleKey;
}) {
  const isAdmin = currentRole === "admin";
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [role, setRole] = useState<string | undefined>();
  const [tool, setTool] = useState<string | undefined>();
  const [status, setStatus] = useState<string | undefined>();

  // 非 admin 固定为当前角色；admin 默认全部，可再按角色过滤
  const effectiveRole = isAdmin ? role : currentRole;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { logs: list } = await agentApi.audit.logs({
        role: effectiveRole,
        tool,
        limit: 100,
      });
      setLogs(list);
    } catch (e) {
      message.error(`加载审计日志失败：${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [effectiveRole, tool]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  // 状态过滤在前端完成（后端接口暂无 status 参数）
  const filtered = useMemo(
    () => (status ? logs.filter((l) => l.status === status) : logs),
    [logs, status],
  );

  const columns: ColumnsType<AuditLogEntry> = [
    {
      title: "时间", dataIndex: "created_at", width: 150,
      render: (v: string) => <Typography.Text style={{ fontSize: 12 }}>{v}</Typography.Text>,
    },
    {
      title: "角色", dataIndex: "role", width: 100,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: "工具", dataIndex: "tool_name", width: 160,
      render: (v: string) => <code style={{ fontSize: 12 }}>{v}</code>,
    },
    {
      title: "状态", dataIndex: "status", width: 80,
      render: (v: string) =>
        v === "success" ? <Tag color="green">成功</Tag> : <Tag color="red">失败</Tag>,
    },
    {
      title: "耗时", dataIndex: "duration_ms", width: 80,
      render: (v: number) => <span style={{ fontSize: 12 }}>{Math.round(v)}ms</span>,
    },
    {
      title: "cache_hit", dataIndex: "cache_hit", width: 90,
      render: (v: boolean) =>
        v ? <Tag color="cyan">命中</Tag> : <Tag>未命中</Tag>,
    },
    {
      title: "摘要", dataIndex: "result_summary", ellipsis: true,
      render: (v: string, row) => (
        <Tooltip title={<pre className="tooltip-pre">{JSON.stringify(row.params, null, 2)}</pre>}>
          <Typography.Text style={{ fontSize: 12 }} ellipsis>{v}</Typography.Text>
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
      width="100%"
      style={{ top: 0, maxWidth: "100%", margin: 0, paddingBottom: 0 }}
      destroyOnClose
    >
      <Space style={{ marginBottom: 12 }} wrap>
        <Select
          allowClear placeholder="全部角色" style={{ width: 140 }} value={effectiveRole}
          disabled={!isAdmin}
          onChange={(v) => setRole(v)}
          options={ROLE_OPTIONS.map((r) => ({ value: r, label: r }))}
        />
        <Select
          allowClear placeholder="全部工具" style={{ width: 180 }} value={tool}
          onChange={(v) => setTool(v)}
          options={TOOL_OPTIONS.map((t) => ({ value: t, label: t }))}
        />
        <Select
          allowClear placeholder="全部状态" style={{ width: 120 }} value={status}
          onChange={(v) => setStatus(v)}
          options={STATUS_OPTIONS}
        />
        <a onClick={() => void load()} style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <ReloadOutlined /> 刷新
        </a>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          共 {filtered.length} 条（最近优先，最多 100{status ? `，按状态「${STATUS_OPTIONS.find((s) => s.value === status)?.label}」过滤` : ""}）
          {!isAdmin && ` · 仅显示 ${currentRole} 角色记录`}
        </Typography.Text>
      </Space>
      <Table<AuditLogEntry>
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={filtered}
        pagination={{ pageSize: 15, showSizeChanger: false }}
        locale={{ emptyText: <Empty description="暂无记录（进行一次对话或工具调用后刷新）" /> }}
        scroll={{ y: "calc(100vh - 260px)", x: 1000 }}
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
