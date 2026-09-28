/**
 * 顶部栏右侧系统入口下拉：
 *   当前角色（只读）/ 切换角色（9 角色小面板）/ 查看可用技能（Drawer）
 *   / 大模型配置（只读 Modal）/ 审计日志（全屏 Modal）
 * 角色与 activeTab 共用 AppShellContext，经 wb.switchRole 统一切换：
 *   → Agent 侧重拉 /skills 并按新角色开新会话；APS 侧 iframe 带 ?role= 重新加载。
 */
import { useState } from "react";
import { Button, Dropdown, Modal } from "antd";
import { DownOutlined } from "@ant-design/icons";
import { ROLES, type RoleKey } from "../types";
import type { Workbench } from "../hooks/useWorkbench";
import SkillsDrawer from "./SkillsDrawer";
import LlmInfoModal from "./LlmInfoModal";
import AuditLogModal from "./AuditLogModal";

export default function SystemMenu({ wb }: { wb: Workbench }) {
  const [roleOpen, setRoleOpen] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [llmOpen, setLlmOpen] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);

  const roleLabel = ROLES.find((r) => r.key === wb.role)?.label ?? wb.role;

  return (
    <>
      <Dropdown
        trigger={["click"]}
        placement="bottomRight"
        menu={{
          items: [
            {
              key: "role-info",
              disabled: true,
              label: (
                <span className="sys-menu-role">
                  当前角色：<b>{roleLabel}</b>
                </span>
              ),
            },
            { type: "divider" },
            { key: "switch", label: "🔄 切换角色" },
            { key: "skills", label: "📋 查看可用技能" },
            { type: "divider" },
            { key: "llm", label: "🤖 大模型配置" },
            { key: "audit", label: "📊 审计日志" },
          ],
          onClick: ({ key }) => {
            if (key === "switch") setRoleOpen(true);
            else if (key === "skills") setSkillsOpen(true);
            else if (key === "llm") setLlmOpen(true);
            else if (key === "audit") setAuditOpen(true);
          },
        }}
      >
        <button type="button" className="topbar-user">
          {roleLabel}
          <DownOutlined className="topbar-user-arrow" />
        </button>
      </Dropdown>

      {/* 切换角色：小面板列出全部 9 个角色（顺序与 APS 侧权限矩阵一致） */}
      <Modal
        title="切换角色"
        open={roleOpen}
        onCancel={() => setRoleOpen(false)}
        footer={<Button onClick={() => setRoleOpen(false)}>关闭</Button>}
        width={440}
      >
        <div className="role-pick">
          {ROLES.map((r) => (
            <button
              key={r.key}
              type="button"
              className={`role-pick-item${r.key === wb.role ? " active" : ""}`}
              onClick={() => {
                wb.switchRole(r.key as RoleKey);
                setRoleOpen(false);
              }}
            >
              <span className="role-pick-label">{r.label}</span>
              <code className="role-pick-key">{r.key}</code>
              {r.key === wb.role && <span className="role-pick-current">当前</span>}
              <span className="role-pick-desc">{r.desc}</span>
            </button>
          ))}
        </div>
      </Modal>

      <SkillsDrawer open={skillsOpen} onClose={() => setSkillsOpen(false)} wb={wb} />
      <LlmInfoModal open={llmOpen} onClose={() => setLlmOpen(false)} wb={wb} />
      <AuditLogModal open={auditOpen} onClose={() => setAuditOpen(false)} currentRole={wb.role} />
    </>
  );
}
