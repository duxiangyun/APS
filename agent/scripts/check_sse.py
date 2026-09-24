"""SSE 事件流一键自检：验证 提问 → 正文（token）→ 工具卡片 → 图表 → done 闭环

用法：python3 scripts/check_sse.py            # 默认跑 4 个用例
     python3 scripts/check_sse.py "问题文本"  # 自定义单问

每个用例使用全新 session_id（uuid4）：agent 侧会话历史为内存态，复用同一 session_id
反复自检会把上一次问答带入上下文，模型可能直接引用历史而不调用工具（误判为 FAIL）。
"""
import json
import sys
import urllib.request
import uuid

AGENT = "http://127.0.0.1:8100"

CASES = [
    ("查看涂装车间的设备负荷", "supervisor", ["get_machine_load"]),
    ("订单7的排产计划是怎么安排的？", "planner", ["get_schedule"]),
    ("有哪些订单延期了？", "planner", ["get_orders"]),
    ("订单2为什么延期？", "planner", ["explain_delay", "get_schedule"]),
]


def stream(message: str, role: str, skills: list[str] | None, sid: str) -> dict:
    body = json.dumps({"message": message, "role": role,
                       "session_id": sid, "skills": skills}).encode()
    req = urllib.request.Request(
        f"{AGENT}/chat/stream", data=body,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    counts: dict[str, int] = {}
    charts: list[str] = []
    summaries: list[str] = []
    text_parts: list[str] = []

    with urllib.request.urlopen(req, timeout=40) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            event = json.loads(payload)
            kind = event.get("type", "?")
            counts[kind] = counts.get(kind, 0) + 1
            if kind == "chart":
                charts.append(f"{event.get('name')}:{event['chart'].get('type')}")
            elif kind in ("delta", "token"):
                # LLM 模式与降级模式统一推 token（react 层把 llm_client 内部的 delta
                # 归一后出网）；这里保留 "delta" 只为兼容归一前的旧后端做诊断。
                text_parts.append(event.get("content", ""))
            elif kind == "tool_result":
                summaries.append(f"{event.get('name')} → {event.get('summary', '')[:60]}")

    return {"counts": counts, "charts": charts, "summaries": summaries,
            "text": "".join(text_parts)[:200]}


def main() -> int:
    cases = ([(sys.argv[1], "planner", None)] if len(sys.argv) > 1 else CASES)
    failed = 0
    for i, (message, role, skills) in enumerate(cases, start=1):
        sid = str(uuid.uuid4())  # 每次全新会话，避免内存历史影响本轮工具调用判定
        try:
            result = stream(message, role, skills, sid)
        except Exception as e:  # noqa: BLE001
            print(f"[{i}] {message}\n    ERROR: {e}")
            failed += 1
            continue
        counts = result["counts"]
        # 判定：闭环完整 + 事件名已归一（归一后正文只应有 token，不应再有 delta 出网）
        ok = (counts.get("done", 0) == 1 and counts.get("tool_result", 0) >= 1
              and counts.get("token", 0) > 0 and counts.get("delta", 0) == 0)
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{i}] {mark} 问：{message}  (role={role}, skills={skills})")
        print(f"    事件统计: {counts}")
        if not ok:
            print("    提示: 判定要求 done==1、tool_result>=1、token>0 且 delta==0；"
                  "delta>0 说明后端未把 delta 归一为 token（前端会丢失回答正文）；"
                  "若 tool_result==0 说明本轮模型未调用工具（LLM 非确定性，可重跑）")
        if result["charts"]:
            print(f"    图表事件: {result['charts']}")
        for summary in result["summaries"]:
            print(f"    工具结果: {summary}")
        print(f"    回复片段: {result['text'][:120]}")
        print()
    print(f"结果：{len(cases) - failed}/{len(cases)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
