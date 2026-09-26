/**
 * 查看可用技能（右侧 Drawer，480px）：
 *   - 展示当前角色的工具列表（工具名 / 描述 / 参数摘要）
 *   - 「对比其他角色」开关：同时拉取并展示另一角色的技能，高亮差异项
 */
import { useCallback, useEffect, useState } from "react";
import { Alert, Drawer, Empty, Select, Space, Spin, Switch, Tag, Typography } from "antd";
import { agentApi } from "../api";
import { ROLES, type RoleKey, type Skill } from "../types";
import type { Workbench } from "../hooks/useWorkbench";

/** 参数摘要：`name*: type, name2: type`（必填标 *） */
function paramSummary(skill: Skill): string {
  const props = skill.parameters?.properties;
  const required = skill.parameters?.required ?? [];
  if (!props || !Object.keys(props).length) return "无参数";
  return Object.entries(props)
    .map(([name, meta]) => `${name}${required.includes(name) ? "*" : ""}: ${meta.type ?? "any"}`)
    .join(", ");
}

function SkillCard({
  skill,
  diffTag,
  highlight,
}: {
  skill: Skill;
  diffTag?: string;
  highlight?: boolean;
}) {
  return (
    <div className={`skill-card${highlight ? " diff" : ""}`}>
      <div className="skill-card-head">
        <code className="skill-card-name">{skill.name}</code>
        {diffTag && <Tag color="orange" style={{ marginInlineEnd: 0 }}>{diffTag}</Tag>}
        {skill.readonly && <Tag style={{ marginInlineEnd: 0 }}>只读</Tag>}
      </div>
      <div className="skill-card-desc">{skill.description}</div>
      <div className="skill-card-params">参数：{paramSummary(skill)}</div>
    </div>
  );
}

export default function SkillsDrawer({
  open,
  onClose,
  wb,
}: {
  open: boolean;
  onClose: () => void;
  wb: Workbench;
}) {
  const [compare, setCompare] = useState(false);
  const [otherRole, setOtherRole] = useState<RoleKey>("manager");
  const [otherSkills, setOtherSkills] = useState<Skill[]>([]);
  const [otherLoading, setOtherLoading] = useState(false);
  const [otherError, setOtherError] = useState<string | null>(null);

  const currentLabel = ROLES.find((r) => r.key === wb.role)?.label ?? wb.role;
  const otherLabel = ROLES.find((r) => r.key === otherRole)?.label ?? otherRole;
  const otherOptions = ROLES.filter((r) => r.key !== wb.role);

  const loadOther = useCallback(async () => {
    setOtherLoading(true);
    setOtherError(null);
    try {
      setOtherSkills(await agentApi.skills(otherRole));
    } catch (e) {
      setOtherError((e as Error).message);
      setOtherSkills([]);
    } finally {
      setOtherLoading(false);
    }
  }, [otherRole]);

  // 开启对比 / 切换对比角色 / 打开抽屉且已开启对比时，拉取另一角色技能
  useEffect(() => {
    if (open && compare) void loadOther();
  }, [open, compare, loadOther]);

  // 对比角色与当前角色撞车时自动纠正
  useEffect(() => {
    if (otherRole === wb.role) {
      const fallback = ROLES.find((r) => r.key !== wb.role);
      if (fallback) setOtherRole(fallback.key);
    }
  }, [otherRole, wb.role]);

  const otherNames = new Set(otherSkills.map((s) => s.name));
  const currentNames = new Set(wb.skills.map((s) => s.name));

  return (
    <Drawer
      title={`可用技能 · ${currentLabel}`}
      open={open}
      onClose={onClose}
      width={480}
      destroyOnClose
    >
      <div className="skills-drawer-toolbar">
        <Space size={8}>
          <Switch
            size="small"
            checked={compare}
            onChange={setCompare}
            aria-label="对比其他角色"
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            对比其他角色
          </Typography.Text>
        </Space>
        {compare && (
          <Select
            size="small"
            style={{ width: 140 }}
            value={otherRole}
            onChange={(v) => setOtherRole(v)}
            options={otherOptions.map((r) => ({ value: r.key, label: r.label }))}
          />
        )}
      </div>

      {wb.skillsError && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message={`加载技能失败：${wb.skillsError}`}
        />
      )}

      <div className="skills-drawer-section">
        <div className="skills-drawer-title">
          {currentLabel}
          <span className="muted">（{wb.skills.length} 个）</span>
        </div>
        {wb.skills.map((s) => (
          <SkillCard
            key={s.name}
            skill={s}
            highlight={compare && !otherNames.has(s.name)}
            diffTag={compare && !otherNames.has(s.name) ? "仅当前角色" : undefined}
          />
        ))}
        {!wb.skills.length && !wb.skillsError && <Empty description="加载中…" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
      </div>

      {compare && (
        <div className="skills-drawer-section">
          <div className="skills-drawer-title">
            {otherLabel}
            <span className="muted">（{otherSkills.length} 个）</span>
          </div>
          {otherError && <Alert type="error" showIcon message={`加载失败：${otherError}`} />}
          {otherLoading && <Spin size="small" />}
          {!otherLoading &&
            !otherError &&
            otherSkills.map((s) => (
              <SkillCard
                key={s.name}
                skill={s}
                highlight={!currentNames.has(s.name)}
                diffTag={!currentNames.has(s.name) ? `仅${otherLabel}` : undefined}
              />
            ))}
        </div>
      )}
    </Drawer>
  );
}
