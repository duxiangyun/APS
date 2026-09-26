/**
 * 左侧栏（240px）：角色切换 / 技能开关 / 连接状态与设置
 */
import { useState } from "react";
import {
  Badge,
  Button,
  Checkbox,
  Divider,
  Modal,
  Segmented,
  Space,
  Tooltip,
  Typography,
} from "antd";
import { ApiOutlined, FileProtectOutlined, ReloadOutlined, SettingOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { AGENT_BASE } from "../api";
import AuditLogModal from "./AuditLogModal";
import LlmConfigModal from "./LlmConfigModal";
import type { Workbench } from "../hooks/useWorkbench";
import { ROLES, type RoleKey, type SkillParam } from "../types";

function skillTooltip(desc: string, params?: Record<string, SkillParam>, required?: string[]): string {
  const lines = [desc];
  if (params && Object.keys(params).length) {
    lines.push("", "参数：");
    for (const [name, meta] of Object.entries(params)) {
      const req = required?.includes(name) ? "（必填）" : "";
      const enums = meta.enum?.length ? ` 可选值: ${meta.enum.join(" / ")}` : "";
      lines.push(`· ${name}${req}: ${meta.type ?? "any"}${enums}`);
      if (meta.description) lines.push(`   ${meta.description}`);
    }
  }
  return lines.join("\n");
}

export default function LeftPanel({ wb }: { wb: Workbench }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [llmOpen, setLlmOpen] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);
  const agentOk = Boolean(wb.health) && !wb.healthError;
  const apsOk = Boolean(wb.health?.aps_connected);
  const llmOk = Boolean(wb.health?.llm_configured);

  return (
    <div className="left-panel">
      <div className="brand">
        <ThunderboltOutlined className="brand-icon" />
        <div>
          <div className="brand-title">APS WorkBuddy</div>
          <div className="brand-sub">智能排产工作台</div>
        </div>
      </div>

      <div className="section">
        <div className="section-title">当前角色</div>
        <Segmented
          vertical
          block
          value={wb.role}
          onChange={(value) => wb.switchRole(value as RoleKey)}
          options={ROLES.map((r) => ({ label: r.label, value: r.key }))}
        />
        <div className="role-desc">{ROLES.find((r) => r.key === wb.role)?.desc}</div>
      </div>

      <Divider style={{ margin: "12px 0" }} />

      <div className="section skills-section">
        <div className="section-title">
          技能
          <span className="muted count">
            {wb.enabledSkills.length}/{wb.skills.length}
          </span>
        </div>
        {wb.skillsError && (
          <Space direction="vertical" size={4} style={{ width: "100%" }}>
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              加载技能失败：{wb.skillsError}
            </Typography.Text>
            <Button size="small" icon={<ReloadOutlined />} onClick={() => window.location.reload()}>
              重试
            </Button>
          </Space>
        )}
        <div className="skill-list">
          {wb.skills.map((skill) => (
            <Tooltip
              key={skill.name}
              placement="right"
              title={
                <pre className="tooltip-pre">
                  {skillTooltip(skill.description, skill.parameters?.properties, skill.parameters?.required)}
                </pre>
              }
            >
              <label className={`skill-item${wb.enabled[skill.name] === false ? " disabled" : ""}`}>
                <Checkbox
                  checked={wb.enabled[skill.name] !== false}
                  onChange={(e) => wb.toggleSkill(skill.name, e.target.checked)}
                />
                <span className="skill-name">{skill.name}</span>
              </label>
            </Tooltip>
          ))}
          {!wb.skills.length && !wb.skillsError && <span className="muted">加载中…</span>}
        </div>
      </div>

      <div className="left-footer">
        <div className="status-row">
          <Badge status={agentOk ? "success" : "error"} text="Agent 后端" />
          <span className="muted">8100</span>
        </div>
        <div className="status-row">
          <Badge status={apsOk ? "success" : "warning"} text="APS 数据" />
          <span className="muted">
            {apsOk ? `run ${wb.health?.aps?.latest_run_id ?? "-"}` : "未连接"}
          </span>
        </div>
        <div className="status-row">
          <Badge status={llmOk ? "success" : "default"} text="LLM" />
          <span className="muted">{llmOk ? String(wb.health?.llm_model ?? "") : "未配置（降级）"}</span>
        </div>
        <Button
          size="small"
          block
          icon={<SettingOutlined />}
          style={{ marginTop: 8 }}
          onClick={() => setSettingsOpen(true)}
        >
          设置
        </Button>
        <Button
          size="small"
          block
          icon={<ApiOutlined />}
          style={{ marginTop: 6 }}
          onClick={() => setLlmOpen(true)}
        >
          大模型配置
        </Button>
        {wb.role === "admin" && (
          <Button
            size="small"
            block
            icon={<FileProtectOutlined />}
            style={{ marginTop: 6 }}
            onClick={() => setAuditOpen(true)}
          >
            审计日志
          </Button>
        )}
      </div>

      <LlmConfigModal
        open={llmOpen}
        onClose={() => setLlmOpen(false)}
        onSaved={wb.refreshHealth}
      />
      <AuditLogModal open={auditOpen} onClose={() => setAuditOpen(false)} currentRole={wb.role} />

      <Modal
        title="设置"
        open={settingsOpen}
        onCancel={() => setSettingsOpen(false)}
        footer={<Button onClick={() => setSettingsOpen(false)}>关闭</Button>}
      >
        <div className="settings-body">
          <div className="settings-row">
            <span className="muted">Agent 地址</span>
            <code>{AGENT_BASE || "(同源)"}</code>
          </div>
          <div className="settings-row">
            <span className="muted">环境变量</span>
            <code>VITE_AGENT_BASE_URL</code>
          </div>
          <div className="settings-row">
            <span className="muted">会话 ID</span>
            <code>{wb.sessionId}</code>
          </div>
          <div className="settings-row">
            <span className="muted">主模型</span>
            <code>{String(wb.health?.llm_model ?? "未配置")}</code>
          </div>
          <div className="settings-row">
            <span className="muted">备用模型</span>
            <code>{String(wb.health?.llm_fallback_model ?? "未配置")}</code>
          </div>
          <div className="settings-row">
            <span className="muted">APS 数据</span>
            <code>
              {apsOk ? `已连接 · 订单 ${String(wb.health?.aps?.orders ?? "-")}` : "未连接"}
            </code>
          </div>
          <Space style={{ marginTop: 12 }}>
            <Button size="small" onClick={wb.refreshHealth}>
              刷新状态
            </Button>
            <Button size="small" danger onClick={wb.resetSession}>
              重置会话
            </Button>
          </Space>
        </div>
      </Modal>
    </div>
  );
}