"""01 · 最小 ReAct Agent（零依赖、零 API Key 可跑）

一次跑通你能看到：
  1. 消息状态（system / user / assistant / tool 四类角色）
  2. 模型输出解析成 tool_calls
  3. 参数校验 + 工具不存在时的错误回填自修正
  4. 观察结果回填，进入下一轮
  5. 三层停止条件：FINISH / 重复动作检测 / 步数与 token 预算熔断
  6. 每一步的 trace（可观测性的最小形态）

运行：
    python code/01_minimal_react_agent.py
接真实模型：
    LLM_API_KEY=xxx python code/01_minimal_react_agent.py
"""
from __future__ import annotations

import ast
import json
import operator
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import LLMOutput, ToolCall, get_client, messages_tokens  # noqa: E402

# ---------------------------------------------------------------- 工具层

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def safe_eval(expr: str) -> float:
    """只允许数字与四则运算，绝不使用 eval 直接执行字符串。"""
    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](visit(node.operand))
        raise ValueError(f"不支持的表达式片段: {ast.dump(node)}")

    return visit(ast.parse(expr, mode="eval"))


_KNOWLEDGE = {
    "ReAct": "ReAct 将推理(Thought)与行动(Action)交错，通过环境观察(Observation)纠正事实错误。",
    "MCP": "MCP 是 Agent 连接工具与数据的标准化协议，基于 JSON-RPC，与 Function Calling 不在同一层。",
    "RAG": "RAG 先检索外部文档再生成答案，检索质量决定答案上限。",
}


def calculator(expression: str) -> str:
    try:
        return str(safe_eval(expression))
    except Exception as exc:  # noqa: BLE001
        return f"计算失败: {exc}"


def search(query: str) -> str:
    hits = [f"{k}: {v}" for k, v in _KNOWLEDGE.items() if k.lower() in query.lower()]
    return "\n".join(hits) if hits else f"未找到与「{query}」相关的内容，请换关键词。"


TOOL_SPECS: dict[str, dict[str, Any]] = {
    "calculator": {
        "name": "calculator",
        "description": "计算一个纯数字四则运算表达式。参数 expression 只能是数字与 + - * / ( ) 等符号。",
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}},
                       "required": ["expression"]},
        "fn": lambda args: calculator(args["expression"]),
    },
    "search": {
        "name": "search",
        "description": "在内部知识库中查询一个概念的定义。参数 query 为关键词。",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                       "required": ["query"]},
        "fn": lambda args: search(args["query"]),
    },
}


def tool_schemas() -> list[dict]:
    return [{"name": s["name"], "description": s["description"], "parameters": s["parameters"]}
            for s in TOOL_SPECS.values()]


def validate(call: ToolCall) -> str | None:
    """返回 None 表示合法，否则返回可指导模型自修正的错误信息。"""
    spec = TOOL_SPECS.get(call.name)
    if spec is None:
        return f"工具「{call.name}」不存在。可用工具: {', '.join(TOOL_SPECS)}"
    schema = spec["parameters"]
    for key in schema.get("required", []):
        if key not in call.arguments:
            return f"缺少必填参数 {key}；该工具的 Schema 为 {json.dumps(schema, ensure_ascii=False)}"
    for key, value in call.arguments.items():
        expected = schema["properties"].get(key, {}).get("type")
        if expected == "string" and not isinstance(value, str):
            return f"参数 {key} 应为 string，实际是 {type(value).__name__}"
    return None


# ---------------------------------------------------------------- Agent Loop

SYSTEM_PROMPT = """你是一个最小 ReAct Agent。每一轮只能输出以下两种格式之一：

TOOL: 工具名 {"参数名": "参数值"}
FINISH: 最终答案

规则：需要外部信息或计算时先调工具；拿到观察结果后再决定下一步；不要重复同一个工具调用；
不要编造工具名；结论必须基于观察结果。"""

DEFAULT_SCRIPT = [
    # 第 1 轮：故意用错工具名，用来演示「错误回填 -> 模型自修正」
    'THOUGHT: 需要先计算 12 * 7\nTOOL: calc {"expression": "12 * 7"}',
    # 第 2 轮：修正工具名
    'THOUGHT: 工具名写错了，改用 calculator\nTOOL: calculator {"expression": "12 * 7"}',
    # 第 3 轮：再查一个概念
    'THOUGHT: 已得到 84，再查一下 ReAct 的定义\nTOOL: search {"query": "ReAct"}',
    # 第 4 轮：给出最终答案
    "FINISH: 12 * 7 = 84。ReAct 是 Thought→Action→Observation 交错的框架，"
    "用环境观察替代凭空猜测，从而纠正事实错误。",
]

LOOP_SCRIPT = [
    'TOOL: search {"query": "RAG"}',
    'TOOL: search {"query": "RAG"}',
    'TOOL: search {"query": "RAG"}',
    'TOOL: search {"query": "RAG"}',
]


def run(question: str, script: list[str] | None = None, *,
        max_steps: int = 8, token_budget: int = 6000, verbose: bool = True):
    """返回 (final_answer, trace)。这就是 Agent 的全部骨架。"""
    llm = get_client(script if script is not None else DEFAULT_SCRIPT)
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    trace: list[dict] = []
    seen_actions: set[str] = set()

    for step in range(1, max_steps + 1):
        # 资源层：整段上下文的 token 预算
        used = messages_tokens(messages)
        if used > token_budget:
            reason = f"token 预算熔断（{used} > {token_budget}）"
            trace.append({"step": step, "event": "budget_exceeded", "detail": reason})
            return f"[强制终止] {reason}", trace

        out: LLMOutput = llm.chat(messages, tools=tool_schemas())
        if verbose:
            print(f"\n--- step {step} ---")
            if out.content:
                print(f"THOUGHT: {out.content}")
            for c in out.tool_calls:
                print(f"ACTION : {c.name} {json.dumps(c.arguments, ensure_ascii=False)}")

        # 语义层：显式 FINISH
        if out.final_answer is not None:
            trace.append({"step": step, "event": "finish", "answer": out.final_answer})
            if verbose:
                print(f"FINISH : {out.final_answer}")
            return out.final_answer, trace

        if not out.tool_calls:
            # 既没给答案也没调工具：把格式要求回填，让模型自己纠偏
            messages.append({"role": "user", "content": "请严格输出 TOOL: ... 或 FINISH: ..."})
            trace.append({"step": step, "event": "format_retry"})
            continue

        # 注意顺序：assistant(tool_calls) 必须在 tool 结果之前
        assistant_msg: dict = {"role": "assistant", "content": out.content, "tool_calls": []}
        messages.append(assistant_msg)

        for i, call in enumerate(out.tool_calls):
            call_id = f"call_{step}_{i}"
            assistant_msg["tool_calls"].append(
                {"id": call_id, "name": call.name, "arguments": call.arguments})

            # 行为层：重复动作检测（不等到 max_steps 才发现绕圈）
            key = json.dumps([call.name, call.arguments], sort_keys=True, ensure_ascii=False)
            if key in seen_actions:
                observation = ("检测到重复动作（相同工具 + 相同参数）。不要重复，"
                               "请换一个思路，或直接输出 FINISH: 说明当前结论。")
                event = "duplicate_action"
            else:
                seen_actions.add(key)
                error = validate(call)
                if error:
                    observation = f"工具调用无效：{error}。请修正后重试。"
                    event = "invalid_call"
                else:
                    try:
                        observation = str(TOOL_SPECS[call.name]["fn"](call.arguments))
                        event = "tool_ok"
                    except Exception as exc:  # noqa: BLE001
                        observation = f"工具执行异常：{exc}"
                        event = "tool_error"

            # 观察回填：这才是 ReAct 里 Observation 的真正含义
            messages.append({"role": "tool", "tool_call_id": call_id,
                             "name": call.name, "content": observation})
            trace.append({"step": step, "event": event, "tool": call.name,
                          "args": call.arguments, "observation": observation})
            if verbose:
                print(f"OBSERVE: {observation}")

    return f"[强制终止] 达到最大轮次 {max_steps}，未产出最终答案", trace


def main() -> None:
    print("=" * 72)
    print("实验 1：完整 ReAct 循环（含工具名写错后的自修正）")
    print("=" * 72)
    answer, trace = run("请计算 12 * 7，并说明 ReAct 是什么")
    print(f"\n最终答案：{answer}")
    print(f"轨迹共 {len(trace)} 条：")
    for t in trace:
        print(f"  step{t['step']} {t['event']:<16} {t.get('tool', '')}")

    print("\n" + "=" * 72)
    print("实验 2：行为层停止条件 —— 重复动作检测")
    print("=" * 72)
    answer2, trace2 = run("反复查同一个东西", script=LOOP_SCRIPT, max_steps=5, verbose=True)
    print(f"\n结果：{answer2}")
    print("事件序列：" + " -> ".join(t["event"] for t in trace2))

    print("\n" + "=" * 72)
    print("实验 3：资源层熔断 —— 把预算调到极小")
    print("=" * 72)
    answer3, _ = run("预算测试", token_budget=1, verbose=False)
    print(answer3)


if __name__ == "__main__":
    main()
