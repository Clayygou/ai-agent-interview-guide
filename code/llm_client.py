"""统一的 LLM 接口。

设计目的：让本仓库所有示例 **零配置、零第三方依赖** 就能跑通。

- 默认使用 ScriptedLLM：按预先写好的「模型输出脚本」返回结果，
  这样可以把「模型输出 -> 解析工具调用 -> 执行 -> 观察回填」的协议看得一清二楚。
- 设置 LLM_API_KEY 后自动切换为 OpenAICompatibleLLM（用标准库 urllib，
  仍然不需要安装 openai 包），可直接跑真实模型。

脚本语法（每行一条）：
    THOUGHT: 这里是一段思考（可省略，会进入 content）
    TOOL: tool_name {"arg": "value"}
    FINISH: 最终答案
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# Windows 控制台默认可能不是 UTF-8，统一处理，避免中文输出报错
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # pragma: no cover
    pass


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str = ""


@dataclass
class LLMOutput:
    content: str = ""                      # 思考 / 普通文本
    tool_calls: list[ToolCall] = field(default_factory=list)
    final_answer: str | None = None        # 非 None 表示 Agent 应当结束


def parse_scripted(text: str) -> LLMOutput:
    """把教学脚本解析成统一的 LLMOutput。"""
    thoughts: list[str] = []
    calls: list[ToolCall] = []
    final: str | None = None
    for raw in text.strip().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("TOOL:"):
            rest = line[len("TOOL:"):].strip()
            name, _, args = rest.partition(" ")
            try:
                arguments = json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                arguments = {"_raw": args}
            if not isinstance(arguments, dict):
                arguments = {"_raw": args}
            calls.append(ToolCall(name=name.strip(), arguments=arguments))
        elif line.startswith("FINISH:"):
            final = line[len("FINISH:"):].strip()
        elif line.startswith("THOUGHT:"):
            thoughts.append(line[len("THOUGHT:"):].strip())
        else:
            thoughts.append(line)
    return LLMOutput(content="\n".join(thoughts), tool_calls=calls, final_answer=final)


class ScriptedLLM:
    """按脚本依次返回模型输出，并留存每轮上下文，便于调试与回放。"""

    def __init__(self, script: list[str]):
        self.script = list(script)
        self.history: list[list[dict]] = []

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMOutput:
        self.history.append([dict(m) for m in messages])
        if not self.script:
            return LLMOutput(
                content="(脚本已耗尽：模型未能在预算内给出答案)",
                final_answer="(预算耗尽，未能完成，请转人工或调整停止条件)",
            )
        return parse_scripted(self.script.pop(0))


def to_openai_messages(messages: list[dict]) -> list[dict]:
    """把仓库内部消息格式转换为 OpenAI Chat Completions 格式。"""
    out: list[dict] = []
    for m in messages:
        role = m["role"]
        if role == "assistant" and m.get("tool_calls"):
            calls = []
            for i, c in enumerate(m["tool_calls"]):
                calls.append({
                    "id": c.get("id") or f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": c["name"],
                        "arguments": json.dumps(c.get("arguments", {}), ensure_ascii=False),
                    },
                })
            out.append({"role": "assistant", "content": m.get("content") or None, "tool_calls": calls})
        elif role == "tool":
            out.append({"role": "tool", "tool_call_id": m.get("tool_call_id", ""),
                        "content": str(m.get("content", ""))})
        else:
            out.append({"role": role, "content": str(m.get("content", ""))})
    return out


class OpenAICompatibleLLM:
    """真实模型：任何兼容 /chat/completions 的服务都可以。"""

    def __init__(self) -> None:
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMOutput:
        payload: dict[str, Any] = {"model": self.model, "messages": to_openai_messages(messages)}
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        msg = data["choices"][0]["message"]
        calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            raw = fn.get("arguments", "{}")
            try:
                args = json.loads(raw)
            except json.JSONDecodeError:
                args = {"_raw": raw}
            calls.append(ToolCall(name=fn.get("name", ""), arguments=args, id=tc.get("id", "")))
        content = msg.get("content") or ""
        return LLMOutput(content=content, tool_calls=calls,
                         final_answer=None if calls else content)


def get_client(script: list[str] | None = None):
    """有 LLM_API_KEY 就用真实模型，否则用脚本模型。"""
    if os.getenv("LLM_API_KEY"):
        return OpenAICompatibleLLM()
    return ScriptedLLM(script or [])


def approx_tokens(text: str) -> int:
    """粗略估算 token 数：中文按 1 字 1 token，其余按 4 字符 1 token。"""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return max(1, cjk + (len(text) - cjk) // 4)


def messages_tokens(messages: list[dict]) -> int:
    return sum(approx_tokens(json.dumps(m, ensure_ascii=False)) for m in messages)
