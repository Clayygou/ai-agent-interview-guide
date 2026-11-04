"""06 · MCP Client（启动 Server 子进程，走一遍真实 stdio 握手）

对应 03 章。你会看到：
    initialize（能力协商） -> notifications/initialized
    -> tools/list（能力发现） -> tools/call（执行） -> resources/read

运行：python code/06_mcp_client.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVER = HERE / "05_mcp_server.py"


class MCPClient:
    def __init__(self):
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER), "--stdio"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )
        self.next_id = 1

    def request(self, method: str, params: dict | None = None) -> dict:
        """一问一答；真实客户端还要处理通知、并发 id 与 SSE 流式。"""
        payload = {"jsonrpc": "2.0", "id": self.next_id, "method": method,
                   "params": params or {}}
        self.next_id += 1
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps(payload, ensure_ascii=True) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"Server 提前退出：{err}")
        return json.loads(line)

    def notify(self, method: str) -> None:
        """通知没有 id，也不需要响应。"""
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}, ensure_ascii=True) + "\n")
        self.proc.stdin.flush()

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.terminate()


def main() -> None:
    print("=" * 72)
    print("06 · MCP Client：真实子进程 + stdio + JSON-RPC")
    print("=" * 72)

    client = MCPClient()
    try:
        init = client.request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "demo-client", "version": "0.1.0"},
        })
        print("\n[1] initialize ->")
        print("   ", json.dumps(init["result"], ensure_ascii=False))
        client.notify("notifications/initialized")
        print("[2] 已发送 notifications/initialized（通知无响应）")

        tools = client.request("tools/list")["result"]["tools"]
        print(f"\n[3] tools/list -> 发现 {len(tools)} 个工具：")
        for t in tools:
            print(f"    - {t['name']}: {t['description']}")

        ok = client.request("tools/call", {"name": "get_weather", "arguments": {"city": "上海"}})
        print("\n[4] tools/call（合法参数）->")
        print("   ", json.dumps(ok["result"], ensure_ascii=False))

        bad = client.request("tools/call", {"name": "add", "arguments": {"a": "1", "b": 2}})
        print("\n[5] tools/call（参数类型错）->")
        print("   ", json.dumps(bad["result"], ensure_ascii=False))
        print("    ↑ 错误信息要足够具体，才能回填给模型让它自修正")

        res = client.request("resources/read", {"uri": "note://policy"})
        print("\n[6] resources/read ->")
        print("   ", json.dumps(res["result"], ensure_ascii=False))

        missing = client.request("unknown/method")
        print("\n[7] 未知方法 ->")
        print("   ", json.dumps(missing.get("error"), ensure_ascii=False))
    finally:
        client.close()

    print("\n" + "=" * 72)
    print("要点：Client 与 Server 是 1:1 连接；Host（Agent 应用）可同时管理多个 Client。")
    print("换成远程服务时，stdio 换成 Streamable HTTP，JSON-RPC 消息体完全一样。")
    print("=" * 72)


if __name__ == "__main__":
    main()
