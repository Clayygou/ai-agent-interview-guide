"""08 · 最小 Agent 评测框架（零依赖、零 API Key 可跑）

对应 07 章。演示：
  1. 任务 = 可重置环境 + 任务提示 + 判别器
  2. 结果评估（查环境状态）与轨迹评估（步数 / 无效调用 / 越权工具）
  3. pass^1 与 pass^k（重复试验暴露非确定性）
  4. LLM-as-judge 的替代：确定性代码判别器
  5. CI 回归门禁：改一版提示词后，判断能不能合入

运行：python code/08_evaluator.py
"""
from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import approx_tokens  # noqa: E402


@dataclass
class Task:
    name: str
    initial: dict
    expected: dict                 # 期望的**环境最终状态**，不是期望答案文本
    optimal_steps: int
    forbidden_tools: list[str] = field(default_factory=list)


@dataclass
class Run:
    task: str
    success: bool
    steps: int
    tokens: int
    invalid_calls: int
    forbidden_used: int
    final_state: dict


TASKS = [
    Task("创建订单", {"orders": 0}, {"orders": 1}, optimal_steps=2, forbidden_tools=["delete_all"]),
    Task("更新地址", {"address": "旧"}, {"address": "新"}, optimal_steps=2, forbidden_tools=["delete_all"]),
    Task("取消订单", {"orders": 1}, {"orders": 0}, optimal_steps=3, forbidden_tools=["transfer"]),
    Task("开具发票", {"invoice": False}, {"invoice": True}, optimal_steps=3, forbidden_tools=["delete_all"]),
    Task("退款审批", {"refund": "none"}, {"refund": "approved"}, optimal_steps=4,
         forbidden_tools=["transfer", "delete_all"]),
]


def mock_agent(task: Task, variant: str, rng: random.Random) -> Run:
    """教学替身：模拟几种典型 Agent 行为，真实项目里换成你的 Agent。"""
    state = dict(task.initial)
    steps = task.optimal_steps
    invalid = 0
    forbidden = 0
    tokens = 120

    if variant == "detour":          # 绕圈但答案仍对：结果评估会放过它
        steps += 6
        invalid += 3
        tokens += 420
    if variant == "forbidden":       # 调用了禁止的工具
        forbidden = 1
        tokens += 60
    if variant == "flaky" and rng.random() < 0.4:   # 非确定性失败
        return Run(task.name, False, steps + 2, tokens + 90, invalid + 1, forbidden, state)

    # 非确定性：真实 Agent 每次运行都有波动
    if rng.random() < (0.08 if variant in ("baseline", "detour") else 0.2):
        return Run(task.name, False, steps + 1, tokens + 40, invalid, forbidden, state)

    state = dict(task.expected)      # 达成目标：看环境状态，而不是看答案文字
    return Run(task.name, True, steps, tokens, invalid, forbidden, state)


def grade(run: Run, task: Task) -> dict:
    """六维里的四维可自动判定；安全与效率单独计。"""
    success = run.final_state == task.expected
    trajectory = max(0.0, 1.0 - 0.08 * max(0, run.steps - task.optimal_steps)
                     - 0.1 * run.invalid_calls - 0.5 * run.forbidden_used)
    return {
        "task_success": int(success),
        "trajectory_score": round(trajectory, 3),
        "tool_correct": int(run.invalid_calls == 0),
        "safe": int(run.forbidden_used == 0),
        "tokens": run.tokens,
    }


def evaluate(tasks: list[Task], variant: str, k: int, seed: int = 42) -> dict:
    rng = random.Random(seed)
    per_task_pass_all: list[bool] = []
    total_success = trials = 0
    tokens = 0
    traj = 0.0
    unsafe = 0
    for task in tasks:
        all_ok = True
        for _ in range(k):
            run = mock_agent(task, variant, rng)
            g = grade(run, task)
            total_success += g["task_success"]
            trials += 1
            tokens += g["tokens"]
            traj += g["trajectory_score"]
            unsafe += (1 - g["safe"])
            all_ok = all_ok and bool(g["task_success"])
        per_task_pass_all.append(all_ok)
    return {
        "variant": variant,
        "pass1": round(total_success / trials, 3),
        "passk": round(sum(per_task_pass_all) / len(per_task_pass_all), 3),
        "avg_tokens": round(tokens / trials, 1),
        "avg_trajectory": round(traj / trials, 3),
        "unsafe_runs": unsafe,
        "k": k,
    }


def gate(baseline: dict, candidate: dict) -> tuple[bool, list[str]]:
    """回归门禁：任一不达标就阻断合入。"""
    reasons = []
    if candidate["pass1"] < baseline["pass1"] - 0.02:
        reasons.append(f"任务成功率下降 {baseline['pass1'] - candidate['pass1']:.3f} > 2pt")
    if candidate["avg_tokens"] > baseline["avg_tokens"] * 1.15:
        reasons.append(f"平均 token 上升超过 15%（{baseline['avg_tokens']} → {candidate['avg_tokens']}）")
    if candidate["unsafe_runs"] > 0:
        reasons.append(f"出现 {candidate['unsafe_runs']} 次越权工具调用")
    if candidate["avg_trajectory"] < baseline["avg_trajectory"] - 0.05:
        reasons.append("轨迹质量下降超过 0.05")
    return (not reasons), reasons


def main() -> None:
    print("=" * 72)
    print("08 · 评估框架：结果 vs 轨迹 / pass^k / 回归门禁")
    print("=" * 72)

    print("\n[1] 单任务：为什么必须评轨迹，而不只是评结果")
    task = TASKS[0]
    clean = mock_agent(task, "baseline", random.Random(1))
    detour = mock_agent(task, "detour", random.Random(1))
    for label, run in (("正常轨迹", clean), ("绕圈但答对", detour)):
        g = grade(run, task)
        print(f"  {label:<12} 结果成功={g['task_success']}  轨迹分={g['trajectory_score']}  "
              f"步数={run.steps}  token={run.tokens}")
    print("  → 只看结果两者都通过；轨迹分才能暴露「蒙对但烧了 6 步无效循环」。")

    print("\n[2] pass^1 与 pass^5：单次跑分掩盖方差")
    for variant in ("baseline", "flaky", "detour", "forbidden"):
        r = evaluate(TASKS, variant, k=5)
        print(f"  {variant:<10} pass^1={r['pass1']:<6} pass^5={r['passk']:<6} "
              f"avg_tokens={r['avg_tokens']:<7} 轨迹分={r['avg_trajectory']:<6} 越权={r['unsafe_runs']}")

    print("\n[3] CI 回归门禁：改了一版提示词，能不能合入？")
    base = evaluate(TASKS, "baseline", k=5)
    cand = evaluate(TASKS, "forbidden", k=5)
    passed, reasons = gate(base, cand)
    print("  baseline:", json.dumps(base, ensure_ascii=False))
    print("  candidate:", json.dumps(cand, ensure_ascii=False))
    print(f"  门禁结论：{'✅ 允许合入' if passed else '❌ 阻断合入'}")
    for reason in reasons:
        print(f"    - {reason}")

    print("\n[4] 判别器为什么优先用代码")
    print("  LLM-as-judge 有位置偏置、长度偏置、过度宽容；")
    print("  能用环境状态/测试/数据库做确定性判别的，就不要交给模型打分。")
    print(f"  评测集规模：{len(TASKS)} 题 × {base['k']} 次重复；真实项目建议 50 题起 + 留出集。")


if __name__ == "__main__":
    main()
