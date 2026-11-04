"""02 · Function Calling 全链路（零依赖、零 API Key 可跑）

演示重点：
  1. 工具 Schema 的定义与注入
  2. 模型只输出结构化参数，执行永远在应用层
  3. 参数缺失 / 类型错误 -> 明确错误回填 -> 模型自修正 -> 有限重试
  4. 工具结果以 role=tool + tool_call_id 回填
  5. 重试上限与降级（不要无限重试）

运行：python code/02_function_calling.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import get_client, messages_tokens  # noqa: E402

# ---------------------------------------------------------------- 工具定义

ORDERS = {
    "A-1001": {"status": "已发货", "eta": "2026-11-06", "amount": 299},
    "A-1002": {"status": "待付款", "eta": "-", "amount": 88},
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_order",
        "description": "按订单号查询订单状态。订单号形如 A-1001。仅在用户明确询问订单时使用。",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "订单号"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "add",
        "description": "把两个数字相加。",
        "parameters": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
]

TOOL_FNS = {
    "get_order": lambda a: json.dumps(ORDERS.get(a["order_id"], {"error": "订单不存在"}), ensure_ascii=False),
    "add": lambda a: str(a["a"] + a["b"]),
}


def validate(name: str, args: dict) -> str | None:
    """一个极简的 Schema 校验器（生产用 jsonschema / pydantic）。"""
    spec = next((t for t in TOOLS if t["name"] == name), None)
    if spec is None:
        return f"工具「{name}」不存在，可用工具：{', '.join(t['name'] for t in TOOLS)}"
    schema = spec["parameters"]
    for key in schema.get("required", []):
        if key not in args:
            return f"缺少必填参数 '{key}'，Schema：{json.dumps(schema, ensure_ascii=False)}"
    for key, value in args.items():
        prop = schema["properties"].get(key)
        if prop is None:
            return f"未知参数 '{key}'"
        expected = prop["type"]
        ok = ((expected == "string" and isinstance(value, str))
              or (expected == "number" and isinstance(value, (int, float)) and not isinstance(value, bool)))
        if not ok:
            return f"参数 '{key}' 类型错误，期望 {expected}，实际 {type(value).__name__}"
    return None


# 脚本刻意包含三次失败：缺参数 -> 类型错 -> 参数写对
SCRIPT = [
    'THOUGHT: 用户问订单，我需要查一下\nTOOL: get_order {}',
    'THOUGHT: 少了 order_id，补上\nTOOL: add {"a": "1", "b": 2}',
    'THOUGHT: 我不该调 add，而且类型也错了。重新查订单\nTOOL: get_order {"order_id": "A-1001"}',
    "FINISH: 订单 A-1001 已发货，预计 2026-11-06 送达，金额 299 元。",
]


def run(question: str, max_retries: int = 3, max_steps: int = 8) -> str:
    llm = get_client(SCRIPT)
    messages: list[dict] = [
        {"role": "system", "content":
            "你可以调用工具。需要工具时输出 'TOOL: 工具名 {JSON参数}'，"
            "任务完成时输出 'FINISH: 答案'。参数必须严格符合工具 Schema。"},
        {"role": "user", "content": question},
    ]
    retries = 0

    for step in range(1, max_steps + 1):
        out = llm.chat(messages, tools=TOOLS)
        print(f"\n[step {step}] 模型输出：{out.content or '(无思考)'}")
        for c in out.tool_calls:
            print(f"           tool_call -> {c.name}({json.dumps(c.arguments, ensure_ascii=False)})")

        if out.final_answer is not None:
            print(f"\n最终答案：{out.final_answer}")
            return out.final_answer

        if not out.tool_calls:
            messages.append({"role": "user", "content": "请输出 TOOL: ... 或 FINISH: ..."})
            continue

        assistant = {"role": "assistant", "content": out.content, "tool_calls": []}
        messages.append(assistant)
        for i, call in enumerate(out.tool_calls):
            cid = f"call_{step}_{i}"
            assistant["tool_calls"].append(
                {"id": cid, "name": call.name, "arguments": call.arguments})
            error = validate(call.name, call.arguments)
            if error:
                retries += 1
                if retries > max_retries:
                    observation = "重试次数已耗尽，停止重试并转人工。"
                    print(f"           [降级] {observation}")
                else:
                    observation = f"参数校验失败（第 {retries} 次）：{error}"
                    print(f"           [回填错误] {observation}")
            else:
                try:
                    observation = TOOL_FNS[call.name](call.arguments)
                    print(f"           [执行结果] {observation}")
                except Exception as exc:  # noqa: BLE001
                    observation = f"工具执行异常：{exc}"
            messages.append({"role": "tool", "tool_call_id": cid,
                             "name": call.name, "content": observation})

    print(f"\n[降级] 达到最大轮次，上下文约 {messages_tokens(messages)} tokens")
    return "[未能完成，已转人工]"


def main() -> None:
    print("=" * 72)
    print("Function Calling 全链路：Schema -> 输出 -> 校验 -> 错误回填 -> 执行 -> 观察 -> 答案")
    print("=" * 72)
    print("\n工具 Schema：")
    for t in TOOLS:
        print(f"  {t['name']}: {json.dumps(t['parameters'], ensure_ascii=False)}")
    run("帮我查一下订单 A-1001 的状态")


if __name__ == "__main__":
    main()
