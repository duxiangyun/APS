"""角色差异一键自检：同一问题在 manager / planner 下回答应明显不同

验收点（同一句「订单2为什么延期？」）：
  manager → 结论 + KPI 影响 + 引导切换角色，不含设备工序明细（工序段名以 "OP-" 标识）
  planner → 完整归因 + 证据链，且比 manager 更细

用法：python3 scripts/check_roles.py
      python3 scripts/check_roles.py "订单2为什么延期？"
前提：agent（8100，LLM 已配置）与 aps（8000）均在运行。
"""
import json
import re
import sys
import urllib.request
import uuid

AGENT = "http://127.0.0.1:8100"
QUESTION = "订单2为什么延期？"

# manager 回答必须命中：KPI 影响关键词；主动引导切换角色
_KPI_KEYS = ("罚金", "准交率", "延期单", "利润")
_SWITCH_KEYS = ("切换", "计划员", "数据分析师")
# 工序明细标识（设备工序段名形如「装配1 · OP-底盘装配」），manager 不应出现
_DETAIL_RE = re.compile(r"OP-|工序明细|resource_tasks")
# planner 回答必须命中：证据链关键词
_EVIDENCE_KEYS = ("证据", "影子价格", "影价", "满负荷", "达成")


def ask(message: str, role: str) -> dict:
    # 每次调用使用全新 session_id：避免 agent 侧内存会话历史把上一次问答带入上下文，
    # 导致模型直接引用历史而不调用工具（误判为角色差异不生效）
    body = json.dumps({"message": message, "role": role,
                       "session_id": str(uuid.uuid4())}).encode()
    req = urllib.request.Request(f"{AGENT}/chat/stream", data=body,
                                 headers={"Content-Type": "application/json",
                                          "Accept": "text/event-stream"})
    tools: list[str] = []
    text: list[str] = []
    with urllib.request.urlopen(req, timeout=120) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            event = json.loads(payload)
            kind = event.get("type")
            if kind == "tool_call":
                tools.append(event.get("name", ""))
            elif kind in ("delta", "token"):
                text.append(event.get("content", ""))
    return {"tools": tools, "text": "".join(text)}


def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 else QUESTION
    failed = 0

    for role in ("manager", "planner"):
        try:
            out = ask(question, role)
        except Exception as e:  # noqa: BLE001
            print(f"[{role}] ERROR: {e}")
            failed += 1
            continue

        text = out["text"]
        checks: dict[str, bool] = {"调用 explain_delay": "explain_delay" in out["tools"]}
        if role == "manager":
            checks["含 KPI 影响"] = any(k in text for k in _KPI_KEYS)
            checks["引导切换角色"] = any(k in text for k in _SWITCH_KEYS)
            checks["不含设备工序明细"] = not _DETAIL_RE.search(text)
        else:
            checks["含证据链"] = any(k in text for k in _EVIDENCE_KEYS)
            checks["引用交期对比"] = "第2期" in text and "第4期" in text

        ok = all(checks.values())
        failed += 0 if ok else 1
        print("=" * 72)
        print(f"[{role}] {'PASS' if ok else 'FAIL'}  问题：{question}")
        print(f"    工具调用: {out['tools']}")
        for name, passed in checks.items():
            print(f"    {'✓' if passed else '✗'} {name}")
        print(f"    回答长度: {len(text)} 字")
        print(f"    回答: {text}")
        print()

    print(f"结果：{2 - failed}/2 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
