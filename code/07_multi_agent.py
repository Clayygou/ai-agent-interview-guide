"""07 · Orchestrator-Workers 多智能体（零依赖、零 API Key 可跑）

对应 06 章。演示：
  1. 主 Agent 动态拆解子任务（生产里由模型生成，这里用确定性计划便于复现）
  2. 每个 Worker 拥有 **独立上下文与独立工具白名单**（隔离）
  3. 并行 fan-out + 超时 + 失败回退（部分结果 + 说明）
  4. 只转发摘要而非完整轨迹，控制汇总时的上下文膨胀
  5. 全程 token 记账，直观看到成本随 fan-out 非线性增长

运行：python code/07_multi_agent.py
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import approx_tokens  # noqa: E402

SYSTEM_PROMPT = "你是调研子 Agent，只负责分配给你的单一子任务，输出结构化结论。"
KNOWLEDGE = {
    "架构": "主流架构：Supervisor、Pipeline、Orchestrator-Workers、Handoff、Debate。",
    "成本": "多 Agent 约消耗普通聊天 15 倍 token，成本随 fan-out 与交接深度非线性增长。",
    "评估": "评估要覆盖任务成功、轨迹质量、工具正确性、效率、可靠性、安全六个维度。",
    "安全": "高危工具需分级、最小权限、人工审批与幂等设计。",
    "记忆": "记忆分工作、情景、语义、程序性四层，压缩需保留不可丢清单。",
    "协议": "MCP 管 Agent 连工具，A2A 管 Agent 找 Agent，两者分层互补。",
}


@dataclass
class WorkerResult:
    task_id: str
    agent: str
    status: str                 # ok / timeout / error
    summary: str
    evidence: str = ""
    tokens: int = 0
    steps: int = 0
    error: str = ""


@dataclass
class Budget:
    limit: int
    used: int = 0

    def charge(self, n: int) -> None:
        self.used += n

    def ok(self) -> bool:
        return self.used < self.limit


def worker(task_id: str, topic: str, tools: list[str], budget: Budget,
           fail: bool = False, slow: bool = False) -> WorkerResult:
    """子 Agent：独立 messages、独立工具集、独立 token 计量。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + f" 你的可用工具：{', '.join(tools)}"},
        {"role": "user", "content": f"请调研：{topic}"},
    ]
    spent = approx_tokens(messages[0]["content"]) + approx_tokens(messages[1]["content"])

    if slow:
        time.sleep(3)
    if fail:
        return WorkerResult(task_id, f"worker-{topic}", "error", "", tokens=spent,
                            steps=1, error="模拟：检索源不可用")

    assert "search" in tools, "权限隔离生效：该 worker 无 search 工具"
    evidence = KNOWLEDGE.get(topic, f"未找到「{topic}」的资料")
    observation = f"[tool:search] {evidence}"
    messages.append({"role": "tool", "content": observation})
    spent += approx_tokens(observation)
    summary = f"{topic}：{evidence[:28]}…"
    spent += approx_tokens(summary) + 20  # 生成开销
    budget.charge(spent)
    # 关键：回传的是 **摘要**，不是完整 messages 轨迹
    return WorkerResult(task_id, f"worker-{topic}", "ok", summary, evidence, spent, steps=2)


def plan(question: str, topics: list[str]) -> list[dict]:
    """生产里由主 Agent 动态生成；这里固定，便于观察机制。"""
    return [{"id": f"T{i+1}", "topic": t, "tools": ["search", "summarize"]}
            for i, t in enumerate(topics)]


def orchestrate(question: str, topics: list[str], *, fail_index: int | None = None,
                slow_index: int | None = None, timeout: float = 1.5,
                budget_limit: int = 3000, verbose: bool = True) -> tuple[str, list[WorkerResult], Budget]:
    tasks = plan(question, topics)
    budget = Budget(budget_limit)
    budget.charge(approx_tokens(question) + approx_tokens(str(tasks)))  # 主 Agent 规划开销
    if verbose:
        print(f"  主 Agent 拆解出 {len(tasks)} 个子任务：{[t['topic'] for t in tasks]}")

    results: list[WorkerResult] = []
    with ThreadPoolExecutor(max_workers=len(tasks) or 1) as pool:
        futures = {}
        for i, t in enumerate(tasks):
            futures[pool.submit(worker, t["id"], t["topic"], t["tools"], budget,
                                fail=(i == fail_index), slow=(i == slow_index))] = t
        for future, t in futures.items():
            try:
                results.append(future.result(timeout=timeout))
            except FutureTimeout:
                results.append(WorkerResult(t["id"], f"worker-{t['topic']}", "timeout",
                                            "", tokens=0, steps=0, error="子任务超时"))
            except Exception as exc:  # noqa: BLE001
                results.append(WorkerResult(t["id"], f"worker-{t['topic']}", "error",
                                            "", tokens=0, steps=0, error=str(exc)))

    # 汇总：只吃摘要，不把每个 worker 的完整轨迹塞进主 Agent 窗口
    ok = [r for r in results if r.status == "ok"]
    bad = [r for r in results if r.status != "ok"]
    summary_prompt = "\n".join(f"- {r.summary}" for r in ok)
    budget.charge(approx_tokens(summary_prompt) + 40)

    if verbose:
        for r in results:
            flag = "OK " if r.status == "ok" else "FAIL"
            print(f"  [{flag}] {r.task_id} {r.agent:<14} steps={r.steps} tokens={r.tokens} "
                  f"{r.error or r.summary}")

    answer = f"基于 {len(ok)}/{len(tasks)} 个子任务的结论：\n{summary_prompt}"
    if bad:
        answer += "\n[降级说明] 部分子任务未完成：" + "；".join(f"{r.task_id} {r.error}" for r in bad)
    if not budget.ok():
        answer += f"\n[预算告警] 已消耗 {budget.used}/{budget.limit} tokens"
    return answer, results, budget


def main() -> None:
    print("=" * 72)
    print("07 · Orchestrator-Workers：并行 / 隔离 / 失败回退 / token 记账")
    print("=" * 72)

    print("\n[实验 1] 正常并行")
    answer, _, budget = orchestrate("多智能体系统该怎么设计", ["架构", "成本", "评估"])
    print(answer)
    print(f"  总消耗：{budget.used} tokens")

    print("\n[实验 2] 一个 worker 失败 + 一个超时（失败回退与降级）")
    answer2, results2, _ = orchestrate("调研 Agent 生产化", ["架构", "成本", "评估", "安全"],
                                       fail_index=1, slow_index=2)
    print(answer2)
    print("  状态分布：", [r.status for r in results2])

    print("\n[实验 3] fan-out 宽度对成本的影响")
    for n in (2, 4, 6, 8):
        topics = (["架构", "成本", "评估", "安全", "记忆", "协议"] * 2)[:n]
        _, _, b = orchestrate("成本测试", topics, verbose=False, timeout=5, budget_limit=10**6)
        print(f"  fan-out={n} -> {b.used:>5} tokens")

    print("\n[实验 4] 转发摘要 vs 转发完整轨迹")
    sample = "".join(KNOWLEDGE.values())
    print(f"  转发完整轨迹约 {approx_tokens(sample) * 3} tokens（每个 worker 都要重发系统提示与工具定义）")
    print(f"  只转发摘要约 {approx_tokens('架构：主流架构包括 Supervisor 等五种…') * 3} tokens")
    print("\n结论：多 Agent 的价值是隔离上下文 + 花够 token，代价是非线性增长的成本与失败面。")


if __name__ == "__main__":
    main()
