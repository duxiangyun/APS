/**
 * 大模型配置弹窗：厂商/模型预设选择 + API Key + 主/备用模型 + 连通性测试
 *
 * - 选择预设后自动填充 base_url 与候选模型；
 * - API Key 仅在填写时提交，留空表示保留已保存的 Key（后端脱敏回显）；
 * - 保存立即生效（后端运行时热加载），保存成功后刷新健康状态。
 */
import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  AutoComplete,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Slider,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { ApiOutlined, ExperimentOutlined, SaveOutlined } from "@ant-design/icons";
import { agentApi } from "../api";
import type { LlmConfigPublic, LlmPreset } from "../types";

interface FormValues {
  provider: string;
  base_url: string;
  api_key: string;
  model: string;
  fallback_model: string;
  temperature: number;
  max_tokens: number;
}

export default function LlmConfigModal({
  open,
  onClose,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  onSaved?: () => void;
}) {
  const [form] = Form.useForm<FormValues>();
  const [presets, setPresets] = useState<LlmPreset[]>([]);
  const [current, setCurrent] = useState<LlmConfigPublic | null>(null);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testOk, setTestOk] = useState<boolean | null>(null);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const cfg = await agentApi.llm.config();
      setCurrent(cfg);
      setPresets(cfg.presets ?? []);
      const preset = (cfg.presets ?? []).find((p) => p.base_url === cfg.base_url);
      form.setFieldsValue({
        provider: preset?.key ?? (cfg.base_url ? "custom" : undefined),
        base_url: cfg.base_url,
        api_key: "",
        model: cfg.model,
        fallback_model: cfg.fallback_model ?? "",
        temperature: cfg.temperature,
        max_tokens: cfg.max_tokens,
      });
      setModels(preset?.models ?? []);
      setTestResult(null);
      setTestOk(null);
    } catch (e) {
      message.error(`加载配置失败：${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    if (open) void loadConfig();
  }, [open, loadConfig]);

  const onProviderChange = (key: string) => {
    const preset = presets.find((p) => p.key === key);
    setModels(preset?.models ?? []);
    if (preset) {
      form.setFieldsValue({ base_url: preset.base_url, model: preset.models[0] ?? "" });
    }
  };

  const doTest = async () => {
    const v = await form.validateFields(["base_url", "api_key", "model"]);
    setTesting(true);
    setTestResult(null);
    try {
      const r = await agentApi.llm.test({
        base_url: v.base_url.trim(),
        api_key: v.api_key?.trim() || undefined,
        model: v.model.trim(),
      });
      if (r.ok) {
        setTestOk(true);
        setTestResult(`连接成功 · ${r.model} · ${r.latency_ms}ms${r.reply ? ` · 回复：${r.reply}` : ""}`);
      } else {
        setTestOk(false);
        setTestResult(r.message ?? "连接失败");
      }
    } catch (e) {
      setTestOk(false);
      setTestResult((e as Error).message);
    } finally {
      setTesting(false);
    }
  };

  const doSave = async () => {
    const v = await form.validateFields();
    setSaving(true);
    try {
      const { ok, config } = await agentApi.llm.save({
        base_url: v.base_url.trim(),
        api_key: v.api_key?.trim() || undefined, // 留空 = 保留原 Key
        model: v.model.trim(),
        fallback_model: (v.fallback_model ?? "").trim(),
        temperature: v.temperature,
        max_tokens: v.max_tokens,
      });
      if (ok) {
        message.success(`已保存：${config.model}（配置立即生效）`);
        onSaved?.();
        onClose();
      } else {
        message.error("保存失败");
      }
    } catch (e) {
      message.error(`保存失败：${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={<Space><ApiOutlined /> 大模型配置</Space>}
      open={open}
      onCancel={onClose}
      confirmLoading={saving}
      okText="保存并生效"
      onOk={doSave}
      destroyOnClose
      width={560}
    >
      <Form form={form} layout="vertical" disabled={loading} style={{ marginTop: 8 }}>
        {current && (
          <Alert
            style={{ marginBottom: 12 }}
            type={current.configured ? "success" : "warning"}
            showIcon
            message={
              current.configured
                ? `当前模型：${current.model}（Key：${current.api_key_masked || "未设置"}）`
                : "未配置 API Key，Agent 处于降级模式（仅工具直查，无自然语言对话）"
            }
          />
        )}

        <Form.Item name="provider" label="服务商预设" style={{ marginBottom: 12 }}>
          <Select
            placeholder="选择后自动填充地址与模型"
            onChange={onProviderChange}
            options={presets.map((p) => ({ value: p.key, label: p.name }))}
            allowClear
          />
        </Form.Item>

        <Form.Item
          name="base_url"
          label="Base URL（OpenAI 兼容）"
          rules={[{ required: true, message: "请输入 Base URL" }]}
        >
          <Input placeholder="https://open.bigmodel.cn/api/paas/v4" />
        </Form.Item>

        <Form.Item
          name="api_key"
          label={
            <Space size={8}>
              API Key
              {current?.has_api_key && (
                <Tag color="blue">已保存 {current.api_key_masked}（留空则不修改）</Tag>
              )}
            </Space>
          }
        >
          <Input.Password placeholder="sk-..." autoComplete="new-password" />
        </Form.Item>

        <Form.Item
          name="model"
          label="主模型"
          rules={[{ required: true, message: "请输入或选择主模型" }]}
        >
          <AutoComplete
            options={models.map((m) => ({ value: m }))}
            placeholder="如 glm-4.7-flash"
            filterOption={(input, option) =>
              String(option?.value ?? "").toLowerCase().includes(input.toLowerCase())
            }
          />
        </Form.Item>

        <Form.Item name="fallback_model" label="备用模型（主模型失败时自动切换，可留空）">
          <AutoComplete
            options={models.map((m) => ({ value: m }))}
            placeholder="如 glm-4.7-flash"
            filterOption={(input, option) =>
              String(option?.value ?? "").toLowerCase().includes(input.toLowerCase())
            }
          />
        </Form.Item>

        <Space size="large" style={{ display: "flex" }}>
          <Form.Item name="temperature" label="Temperature" style={{ width: 220 }}>
            <Slider min={0} max={2} step={0.1} style={{ marginBottom: 4 }} />
          </Form.Item>
          <Form.Item name="max_tokens" label="Max Tokens" style={{ width: 200 }}>
            <InputNumber min={64} max={32768} step={64} style={{ width: "100%" }} />
          </Form.Item>
        </Space>

        <Space style={{ marginTop: 4 }}>
          <Button icon={<ExperimentOutlined />} loading={testing} onClick={doTest}>
            测试连接
          </Button>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            发送一条极小请求验证地址 / Key / 模型可用性
          </Typography.Text>
        </Space>
        {testResult && (
          <Alert
            style={{ marginTop: 10 }}
            type={testOk ? "success" : "error"}
            showIcon
            message={testResult}
          />
        )}
      </Form>

      <div style={{ marginTop: 4, color: "#999", fontSize: 12 }}>
        <SaveOutlined /> 保存后写入 agent/data/llm_config.json 并立即生效，无需重启；
        Key 仅保存在后端，不会回传明文。
      </div>
    </Modal>
  );
}

