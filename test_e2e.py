"""APS Agent E2E 测试脚本：测试 3 个典型问题的端到端响应"""
import json
import urllib.request
import urllib.error

AGENT_URL = "http://127.0.0.1:8100"

def chat_stream(message, session_id, role="planner", skills=None):
    """调用 /chat/stream 并收集所有 SSE 事件"""
    body = json.dumps({
        "message": message,
        "role": role,
        "session_id": session_id,
        "skills": skills,
    }).encode()
    req = urllib.request.Request(
        f"{AGENT_URL}/chat/stream",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events = []
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            buf = ""
            for chunk in resp.read().decode("utf-8", errors="replace").split("\n\n"):
                for line in chunk.split("\n"):
                    line = line.strip()
                    if line.startswith("data: "):
                        payload = line[6:].strip()
                        if payload and payload != "[DONE]":
                            try:
                                events.append(json.loads(payload))
                            except json.JSONDecodeError:
                                pass
    except urllib.error.URLError as e:
        events.append({"type": "error", "message": str(e)})
    return events

def summarize_events(events):
    """提取关键信息用于展示"""
    tools = []
    charts = []
    tokens = []
    errors = []
    for e in events:
        t = e.get("type", "")
        if t == "tool_call":
            tools.append(f"调用: {e.get('name')} params={e.get('arguments')}")
        elif t == "tool_result":
            tools.append(f"结果[{e.get('name')}]: {e.get('summary','')[:200]}")
        elif t == "chart":
            c = e.get("chart", {})
            charts.append(f"图表[{c.get('type')}]: 标题={c.get('title','')[:80]}")
            if c.get("type") == "gantt":
                charts.append(f"  任务数: {len(c.get('tasks',[]))}")
                for tsk in c.get("tasks", [])[:3]:
                    charts.append(f"  - {tsk.get('name','')} [{tsk.get('start')}-{tsk.get('end')}期, 交期:{tsk.get('due')}]")
            if c.get("type") == "load":
                charts.append(f"  设备数: {len(c.get('data',[]))}")
                for r in (c.get('data',[]) or [])[:3]:
                    charts.append(f"  - {r.get('resource_code','')}: 总负荷={r.get('total_load','')}, 产能={r.get('capacity','')}")
            if c.get("type") == "kpi":
                charts.append(f"  KPI项数: {len(c.get('items',[]))}")
                for item in c.get("items", [])[:5]:
                    charts.append(f"  - {item.get('label','')}: {item.get('value','')} {item.get('unit','')}")
        elif t == "error":
            errors.append(f"错误: {e.get('message','')}")
    return {"tools": tools, "charts": charts, "errors": errors}

def run_test(name, message, session_id, skills=None):
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"问题: \"{message}\"")
    print(f"{'='*60}")
    events = chat_stream(message, session_id, skills=skills)
    summary = summarize_events(events)
    print(f"\n--- 工具调用 ({len(summary['tools'])} 步) ---")
    for t in summary["tools"]:
        print(f"  {t}")
    print(f"\n--- 图表事件 ({len(summary['charts'])} 个) ---")
    for c in summary["charts"]:
        print(f"  {c}")
    if summary["errors"]:
        print(f"\n--- 错误 ---")
        for e in summary["errors"]:
            print(f"  {e}")
    print()

if __name__ == "__main__":
    # 测试 1: 今天哪些订单会延期？
    run_test("Q1: 哪些订单会延期？", "今天哪些订单会延期？", "e2e-Q1")

    # 测试 2: 订单 A 为什么延期？ (用 order_id=2)
    run_test("Q2: 订单2为什么延期？", "订单2为什么延期？", "e2e-Q2")

    # 测试 3: CNC-1 这台设备最近负荷怎么样？
    run_test("Q3: CNC-1 负荷", "CNC-1 这台设备最近负荷怎么样？", "e2e-Q3")
