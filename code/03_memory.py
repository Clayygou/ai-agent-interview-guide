"""03 · 分层记忆 + 上下文预算管理（零依赖、零 API Key 可跑）

对应 04 章。核心认知：**模型无状态，messages 列表才是真实记忆**；
上下文工程回答的是「这一轮哪些 token 值得占用窗口，被挤出去的放哪、怎么取回」。

演示：
  1. 四层记忆：工作 / 情景 / 语义 / 程序性
  2. 按 token 预算组装上下文，超预算时渐进压缩
  3. 「不可丢清单」保证压缩不丢目标与约束
  4. 新旧记忆冲突、级联删除
  5. Skills 渐进式披露省了多少 token

运行：python code/03_memory.py
"""
from __future__ import annotations

import json
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import approx_tokens, messages_tokens  # noqa: E402


# ---------------------------------------------------------------- 四层记忆

class ShortTermMemory:
    """工作记忆：最近 N 轮原文。每轮请求都要完整重发，它就是「真实记忆」。"""

    def __init__(self, max_turns: int = 6):
        self.buffer: deque[dict] = deque(maxlen=max_turns)

    def add(self, role: str, content: str) -> None:
        self.buffer.append({"role": role, "content": content})

    def all(self) -> list[dict]:
        return list(self.buffer)

    def drop_oldest(self, n: int) -> list[dict]:
        dropped = []
        for _ in range(min(n, len(self.buffer))):
            dropped.append(self.buffer.popleft())
        return dropped


@dataclass
class Event:
    ts: float
    session: str
    text: str


class EpisodicMemory:
    """情景记忆：带时间戳的事件，用时间范围 / 会话 / 关键词查询。"""

    def __init__(self):
        self.events: list[Event] = []

    def add(self, session: str, text: str) -> None:
        self.events.append(Event(time.time(), session, text))

    def query(self, keyword: str = "", session: str | None = None) -> list[Event]:
        return [e for e in self.events
                if (not keyword or keyword in e.text)
                and (session is None or e.session == session)]


@dataclass
class Fact:
    value: str
    ts: float
    version: int
    source: str


class SemanticMemory:
    """语义记忆：长期事实。生产里换成向量库 + 关系库，这里用 dict 表达语义。"""

    def __init__(self):
        self.facts: dict[str, Fact] = {}
        self.history: dict[str, list[Fact]] = {}

    def upsert(self, key: str, value: str, source: str = "conversation") -> None:
        """冲突处理：带时间戳的新事实覆盖旧事实，但保留版本历史可回溯。"""
        old = self.facts.get(key)
        version = (old.version + 1) if old else 1
        fact = Fact(value, time.time(), version, source)
        self.facts[key] = fact
        self.history.setdefault(key, []).append(fact)
        if old:
            print(f"    [冲突消解] {key}: v{old.version}「{old.value}」 -> v{version}「{value}」")

    def search(self, keyword: str) -> list[str]:
        return [f"{k}={f.value}" for k, f in self.facts.items() if keyword in k or keyword in f.value]

    def delete(self, key: str) -> None:
        """用户要求删除时：事实、历史、派生摘要都要清理（级联删除）。"""
        self.facts.pop(key, None)
        self.history.pop(key, None)


class ProceduralMemory:
    """程序性记忆：Skills。默认只暴露名称与简介，命中后才加载正文。"""

    def __init__(self, skills: dict[str, dict]):
        self.skills = skills

    def summaries(self) -> str:
        return "\n".join(f"- {k}: {v['summary']}" for k, v in self.skills.items())

    def load(self, name: str) -> str:
        return self.skills[name]["body"]


# ---------------------------------------------------------------- 上下文预算

@dataclass
class BuildReport:
    used: int
    budget: int
    compressed: bool = False
    preserved: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


class ContextBuilder:
    """按优先级往有限窗口里放内容；放不下就压缩，但绝不丢「不可丢清单」。"""

    def __init__(self, budget: int):
        self.budget = budget
        self.summary: str = ""      # 压缩产物的落点（外部存储的教学替身）

    def _emit(self, parts: list[dict]) -> tuple[list[dict], int]:
        return parts, messages_tokens(parts)

    def build(self, *, system: str, goal_card: str, short_term: ShortTermMemory,
              retrieved: list[str], skill_summaries: str) -> tuple[list[dict], BuildReport]:
        must_keep = {"goal": goal_card, "system": system}
        base = [
            {"role": "system", "content": system},
            {"role": "system", "content": f"[状态卡 · 不可丢]\n{goal_card}"},
        ]
        optional: list[tuple[str, dict]] = [("skills", {"role": "system", "content": f"可用技能：\n{skill_summaries}"})]
        optional += [(f"retrieved_{i}", {"role": "system", "content": f"[资料 {i+1}] {txt}"})
                     for i, txt in enumerate(retrieved)]
        if self.summary:
            optional.append(("summary", {"role": "system", "content": f"[历史摘要]\n{self.summary}"}))
        optional += [(f"recent_{i}", m) for i, m in enumerate(short_term.all())]

        parts = list(base)
        report = BuildReport(used=messages_tokens(parts), budget=self.budget)
        dropped: list[str] = []
        for tag, msg in optional:
            if report.used + messages_tokens([msg]) <= self.budget:
                parts.append(msg)
                report.used += messages_tokens([msg])
            else:
                dropped.append(tag)

        # 超预算：把被挤出去的历史压缩成结构化摘要（保留不可丢清单）
        if dropped:
            old = short_term.drop_oldest(max(1, len(dropped) // 2))
            if old:
                lines = [f"- {m['role']}: {m['content'][:60]}" for m in old]
                self.summary = (self.summary + "\n" if self.summary else "") + "已确认历史（压缩）：\n" + "\n".join(lines)
                report.compressed = True
                report.dropped = dropped
                # 尝试把摘要塞回去
                summary_msg = {"role": "system", "content": f"[历史摘要]\n{self.summary}"}
                if report.used + messages_tokens([summary_msg]) <= self.budget:
                    parts.append(summary_msg)
                    report.used += messages_tokens([summary_msg])

        # 保真校验：不可丢清单必须逐项仍在
        joined = json.dumps(parts, ensure_ascii=False)
        report.preserved = [k for k, v in must_keep.items() if v in joined]
        if len(report.preserved) != len(must_keep):
            raise RuntimeError("压缩保真校验失败：不可丢清单被破坏")
        return parts, report


def main() -> None:
    print("=" * 72)
    print("03 · 分层记忆与上下文工程")
    print("=" * 72)

    stm = ShortTermMemory(max_turns=6)
    for i in range(6):
        stm.add("user", f"第 {i+1} 轮：请继续分析订单交付日期，注意不要改运费。")
        stm.add("assistant", f"第 {i+1} 轮回复：已记录，继续跟进交付信息。")

    episodic = EpisodicMemory()
    episodic.add("s1", "用户把交付日期改到了 11 月 6 日")
    episodic.add("s1", "用户确认运费保持不变")
    episodic.add("s2", "用户询问发票开具方式")

    semantic = SemanticMemory()
    semantic.upsert("delivery_date", "2026-11-05")
    semantic.upsert("delivery_date", "2026-11-06", source="user_correction")
    semantic.upsert("freight", "不变")

    skills = ProceduralMemory({
        "refund": {"summary": "处理退款申请", "body": "步骤 1 校验订单…（正文约 800 token）" * 20},
        "report": {"summary": "生成周报", "body": "步骤 1 汇总数据…（正文约 800 token）" * 20},
    })

    print("\n[1] 情景记忆按会话查询：")
    for e in episodic.query(session="s1"):
        print("   ", e.text)

    print("\n[2] 语义记忆冲突消解后：", semantic.search("delivery"))
    print("    版本历史：", [(f.version, f.value) for f in semantic.history["delivery_date"]])

    print("\n[3] Skills 渐进式披露的 token 差：")
    print(f"    只放摘要：{approx_tokens(skills.summaries())} tokens")
    print(f"    全量加载：{approx_tokens(skills.summaries() + skills.load('refund') + skills.load('report'))} tokens")

    goal = "目标：确认订单交付日期；约束：不得修改运费；完成标准：给出带出处的结论。"

    print("\n[4] 充足预算下组装上下文：")
    builder = ContextBuilder(budget=3000)
    parts, report = builder.build(system="你是一个客服 Agent。", goal_card=goal,
                                  short_term=stm, retrieved=["订单 A-1001 预计 11-06 送达"],
                                  skill_summaries=skills.summaries())
    print(f"    used={report.used}/{report.budget}, compressed={report.compressed}, "
          f"preserved={report.preserved}, messages={len(parts)}")

    print("\n[5] 极小预算下触发压缩与保真校验：")
    tight = ContextBuilder(budget=420)
    parts2, report2 = tight.build(system="你是一个客服 Agent。", goal_card=goal,
                                  short_term=stm, retrieved=["订单 A-1001 预计 11-06 送达"],
                                  skill_summaries=skills.summaries())
    print(f"    used={report2.used}/{report2.budget}, compressed={report2.compressed}")
    print(f"    被挤出的块：{report2.dropped}")
    print(f"    不可丢清单校验通过：{report2.preserved}")
    print(f"    外部摘要预览：{tight.summary[:80]}...")

    print("\n[6] 用户要求删除记忆（级联）：")
    semantic.delete("delivery_date")
    print("    剩余事实：", semantic.facts)
    print("    版本历史是否清理：", "delivery_date" not in semantic.history)


if __name__ == "__main__":
    main()
