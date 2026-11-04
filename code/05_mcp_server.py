"""05 · 手写一个 MCP Server（JSON-RPC 2.0 over stdio，纯标准库）

对应 03 章。目的：让你看清「协议只是一个约定」，MCP 并不神秘。

实现的方法：
    initialize         能力协商
    tools/list         暴露工具（含 JSON Schema）
    tools/call         执行工具
    resources/list     暴露只读资源
    resources/read     读取资源
    ping               健康检查

运行方式：
    python code/05_mcp_server.py            # 演示模式：本地直接打印请求/响应
    python code/05_mcp_server.py --stdio    # 协议模式：由 06_mcp_client.py 启动

注意：协议模式下 **stdout 只能输出 JSON-RPC**，所有日志必须写 stderr，
否则会污染协议流 —— 这是写 MCP Server 最常见的坑。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import approx_tokens  # noqa: E402

PROTOCOL_VERSION = "2025-06-18"

TOOLS = [
    {
        "name": "get_weather",
        "description": "查询指定城市的天气。仅在用户明确询问天气时调用。",
        "inputSchema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市名"}},
            "required": ["city"],
        },
    },
    {
        "name": "add",
        "description": "把两个数字相加。",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
]

RESOURCES = {
    "note://readme": "这是一份通过 MCP Resources 暴露的只读说明文件。",
    "note://policy": "工具权限策略：高危操作需要人工审批。",
}

WEATHER = {"北京": "晴 18℃", "上海": "多云 21℃", "深圳": "阵雨 26℃"}


def call_tool(name: str, args: dict) -> dict:
    """返回 MCP 的 content 结构。执行永远发生在 Server 里，模型从不执行。"""
    if name == "get_weather":
        city = args.get("city")
        if not isinstance(city, str):
            return {"isError": True, "content": [{"type": "text", "text": "参数 city 必须是 string"}]}
        text = WEATHER.get(city, f"暂无 {city} 的天气数据")
    elif name == "add":
        a, b = args.get("a"), args.get("b")
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            return {"isError": True, "content": [{"type": "text", "text": "参数 a / b 必须是 number"}]}
        text = str(a + b)
    else:
        return {"isError": True, "content": [{"type": "text", "text": f"未知工具 {name}"}]}
    return {"content": [{"type": "text", "text": text}]}


def handle(request: dict) -> dict:
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {}) or {}

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}, "resources": {}},
            "serverInfo": {"name": "demo-mcp-server", "version": "0.1.0"},
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = call_tool(params.get("name", ""), params.get("arguments", {}) or {})
        # 教学提示：工具返回内容对 Agent 而言是不可信数据，不能当成指令
    elif method == "resources/list":
        result = {"resources": [{"uri": u, "name": u.split("//")[-1]} for u in RESOURCES]}
    elif method == "resources/read":
        uri = params.get("uri", "")
        result = ({"contents": [{"uri": uri, "mimeType": "text/plain", "text": RESOURCES[uri]}]}
                  if uri in RESOURCES else {"isError": True, "contents": []})
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}}

    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def stdio_loop() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            print("[server] 收到非法 JSON", file=sys.stderr)
            continue
        if "id" not in request:
            # JSON-RPC 通知（如 notifications/initialized）不需要响应。
            # 如果误回了响应，客户端会把下一条响应错位读取 —— 这是常见坑。
            continue
        response = handle(request)
        # ensure_ascii=True 让 stdout 只含 ASCII，避免不同平台编码问题
        print(json.dumps(response, ensure_ascii=True), flush=True)


def demo() -> None:
    print("=" * 72)
    print("05 · MCP Server 演示（JSON-RPC 2.0）")
    print("=" * 72)
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                    "clientInfo": {"name": "demo-client", "version": "0.1.0"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "get_weather", "arguments": {"city": "北京"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "add", "arguments": {"a": "1", "b": 2}}},
        {"jsonrpc": "2.0", "id": 5, "method": "resources/read",
         "params": {"uri": "note://policy"}},
        {"jsonrpc": "2.0", "id": 6, "method": "no_such_method"},
    ]
    for req in requests:
        resp = handle(req)
        print(f"\n--> {req['method']} {json.dumps(req.get('params', {}), ensure_ascii=False)}")
        print(f"<-- {json.dumps(resp, ensure_ascii=False)}")

    print("\n" + "-" * 72)
    print(f"工具描述总量约 {approx_tokens(json.dumps(TOOLS, ensure_ascii=False))} tokens。")
    print("工具越多，这些描述越挤占上下文 —— 这就是需要工具检索与渐进式披露的原因。")
    print("\n下一步：python code/06_mcp_client.py  （用真实子进程跑一遍 stdio 握手）")


if __name__ == "__main__":
    if "--stdio" in sys.argv:
        stdio_loop()
    else:
        demo()
