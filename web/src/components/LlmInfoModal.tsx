/**
 * 大模型配置（只读 Modal）：
 *   当前模型 / 备用模型 / Base URL（脱敏）/ API Key 状态 / 连接状态
 *   打开时拉取 /llm/config，连接状态复用工作台 health；不做编辑。
 */
import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Descriptions, Modal, Tag, message } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { agentApi } from "../api";
import type { LlmConfigPublic } from "../types";
import type { Workbench } from "../hooks/useWorkbench";

/** Base URL 脱敏：保留 origin 与首个路径段，其余以 **** 代替 */
function maskUrl(raw: string): string {
  if (!raw) return "-";
  try {
    const u = new URL(raw);
    const segs = u.pathname.split("/").filter(Boolean);
    if (!segs.length) return `${u.protocol}//${u.host}`;
    const rest = segs.length > 1 ? "/****" : "";
    return `${u.protocol}//${u.host}/${segs[0]}${rest}`;
  } catch {
    return "****";
  }
}

export default function LlmInfoModal({
  open,
  onClose,
  wb,
}: {
  open: boolean;
  onClose: () => void;
  wb: Workbench;
}) {
  const [cfg, setCfg] = useState<LlmConfigPublic | null>(null);
  const [loading, setLoading] = useState(false);
  // 注意：wb 每次渲染都是新对象，这里只依赖稳定的 refreshHealth，避免 effect 反复触发
  const refreshHealth = wb.refreshHealth;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setCfg(await agentApi.llm.config());
    } catch (e) {
      message.error(`加载配置失败：${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      void load();
      refreshHealth();
    }
  }, [open, load, refreshHealth]);

  const h = wb.health;
  const agentOk = Boolean(h) && !wb.healthError;
  const llmOk = Boolean(h?.llm_configured);
  const apsOk = Boolean(h?.aps_connected);

  return (
    <Modal
      title="大模型配置"
      open={open}
      onCancel={onClose}
      footer={
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>
          刷新
        </Button>
      }
      width={560}
    >
      {loading && !cfg && (
        <Alert type="info" showIcon style={{ marginBottom: 12 }} message="正在加载配置…" />
      )}
      {!cfg?.configured && cfg && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="未配置 API Key，Agent 处于降级模式（仅工具直查，无自然语言对话）"
        />
      )}
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="当前模型">
          {cfg?.model || (h?.llm_model ?? "-")}
        </Descriptions.Item>
        <Descriptions.Item label="备用模型">
          {cfg?.fallback_model || (h?.llm_fallback_model ?? "未设置")}
        </Descriptions.Item>
        <Descriptions.Item label="Base URL（脱敏）">
          <code>{cfg ? maskUrl(cfg.base_url) : "-"}</code>
        </Descriptions.Item>
        <Descriptions.Item label="API Key 状态">
          {cfg?.has_api_key ? (
            <Tag color="green">已配置 {cfg.api_key_masked}</Tag>
          ) : (
            <Tag color="red">未配置</Tag>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="连接状态">
          <span className="llm-status-line">
            <Tag color={agentOk ? "green" : "red"}>Agent 后端 {agentOk ? "正常" : "异常"}</Tag>
            <Tag color={llmOk ? "green" : "orange"}>
              LLM {llmOk ? `已连接 · ${h?.llm_model ?? ""}` : "未配置（降级）"}
            </Tag>
            <Tag color={apsOk ? "green" : "orange"}>APS 数据 {apsOk ? "已连接" : "未连接"}</Tag>
          </span>
        </Descriptions.Item>
      </Descriptions>
      <div className="llm-info-foot">
        只读展示，配置修改请在左侧栏「大模型配置」中操作；Key 仅保存在后端，不会回传明文。
      </div>
    </Modal>
  );
}
