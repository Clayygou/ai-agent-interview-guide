# AI Agent 面试知识库

从 LLM 底座到生产级 Agent：一条「读得懂 → 跑得通 → 讲得清 → 答得上」的学习路径。

为面试准备，也为把知识真正变成自己的。

---

## 学习路径

按编号顺序走。每章统一按「心智模型 → 原理 → 易错点 → 动手 → 面试题」组织。

| # | 阶段 | 回答什么问题 | 配套代码 | 学完你应该能 |
|:--:|---|---|---|---|
| 01 | [LLM 底座](01-llm-foundation/README.md) | 模型到底在做什么？ | — | 讲清 attention / KV Cache / 采样 / 微调对齐 / 推理优化 |
| 02 | [Agent 核心](02-agent-core/README.md) | 一个循环怎么就变成智能体了？ | `01_minimal_react_agent.py` | 手写 ReAct loop，说清停止条件与防死循环 |
| 03 | [工具与协议](03-tools-and-protocols/README.md) | Function Calling、MCP、A2A、Skills 边界在哪？ | `02` `05` `06` | 设计工具 schema，实现 MCP server / client |
| 04 | [记忆与上下文](04-memory-and-context/README.md) | 上下文是有限的，怎么分配？ | `03_memory.py` | 设计分层记忆、压缩与卸载策略 |
| 05 | [RAG](05-rag/README.md) | 为什么检索质量决定答案上限？ | `04_rag_pipeline.py` | 跑通切分 → 混合检索 → 重排 → 生成 → 评估 |
| 06 | [多智能体](06-multi-agent/README.md) | 什么时候真的值得拆多个 Agent？ | `07_multi_agent.py` | 讲清编排模式、隔离与 token 代价 |
| 07 | [评估与可观测](07-eval-and-observability/README.md) | 怎么证明它真的有效？ | `08_evaluator.py` | 搭评测集、评轨迹、定位线上故障 |
| 08 | [安全与生产](08-safety-and-production/README.md) | 上线前必须补哪一层？ | `09_guardrails.py` | 权限、注入防护、HITL、幂等、断点恢复 |

**全局索引**：[学习路线](ROADMAP.md) · [权威资料](RESOURCES.md) · [高频面试题](INTERVIEW.md) · [掌握度自测](CHECKLIST.md) · [代码说明](code/README.md)

---

## 快速开始

```bash
git clone https://github.com/Clayygou/ai-agent-interview-guide.git
cd ai-agent-interview-guide
python code/01_minimal_react_agent.py
```

所有示例默认使用**脚本化 Mock 模型**，不需要 API Key、不需要装框架，零配置跑通，目的是把
「模型输出 → 解析工具调用 → 执行 → 观察回填」这条协议看得一清二楚。
想接真实模型，设置三个环境变量即可，见 [code/README.md](code/README.md)。

## 怎么用这个仓库

1. **读** — 每章 README，重点看「易错点」，那是面试官的追问区
2. **跑** — 对应代码，改参数、故意弄坏它，观察它怎么失败
3. **写** — 合上文档，用自己的话写出关键结论；写不出来就是没掌握
4. **答** — 用章末面试题自测，对照 [CHECKLIST.md](CHECKLIST.md) 打勾
5. **讲** — 能给不懂的人讲明白，才叫真的会

## 这个仓库的取舍

- **中文、面向国内面试**，覆盖 2025–2026 新考点：Harness、上下文工程、Skills、A2A、Agent 评估
- **先手写再用框架**：所有核心机制都有一段不依赖 LangChain / LangGraph 的最小实现
- **题目带追问**：区分「背定义」和「你项目里具体怎么做的」
- **资料只收一手来源**：论文、官方规范、官方工程博客，附在 [RESOURCES.md](RESOURCES.md)

---

MIT License · 持续更新
