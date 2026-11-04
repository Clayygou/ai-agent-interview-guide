# 权威资料清单

> 只收一手来源：论文、官方规范、官方工程博客、可运行的开源项目。
> 标 **必读** 的是面试性价比最高的，先读这些；其余按岗位方向补。

---

## 一、五篇必读（先读完这五篇，再谈框架）

| 优先级 | 资料 | 来源 | 读它解决什么 |
|:--:|---|---|---|
| 必读 ① | [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) | Anthropic, 2024（2026 更新） | Workflow vs Agent 的原始定义、五种工作流模式、「先找最简单方案」、ACI 概念。业界引用密度最高的一篇 |
| 必读 ② | [A Practical Guide to Building Agents (PDF)](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf) | OpenAI, 2025 | 什么时候**不该**做 Agent；单 Agent → 多 Agent 的拆分时机；guardrails 与人工升级 |
| 必读 ③ | [Agents Whitepaper](https://www.kaggle.com/whitepaper-agents) / [Agents Companion](https://www.kaggle.com/whitepaper-agent-companion) | Google / Kaggle | `Agent = 模型 + 工具 + 编排层` 的经典拆解；第二本讲 AgentOps、评估与多智能体（Kaggle 免费账号） |
| 必读 ④ | [LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/) | Lilian Weng, 2023 | 规划 / 记忆 / 工具使用 三分法的源头，几乎所有框架的词汇表来自这里 |
| 必读 ⑤ | [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Anthropic, 2025 | 上下文是有限资源；压缩、结构化笔记、子 Agent、just-in-time 检索四种手段。**2026 面试重灾区** |

配套工程文章（同样出自官方，按主题补）：

- [Writing effective tools for agents — with agents](https://www.anthropic.com/research/writing-tools-for-agents) — 工具描述、返回内容、token 效率，最系统的工具设计指南
- [How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system) — Orchestrator-Workers 的真实工程细节与 token 代价
- [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) — Agent 评测术语与做法
- [OpenAI Agents SDK / Agents 指南](https://platform.openai.com/docs/guides/agents) — handoff、guardrail、tracing 的官方抽象
- [12-Factor Agents](https://github.com/humanlayer/12-factor-agents) — 「自己掌控提示词、上下文与控制流」的 12 条工程原则，适合建立 Harness 思维

---

## 二、经典论文（按脉络读，不要按顺序背）

### 推理与循环

| 论文 | 年份 | 链接 | 一句话 / 面试价值 |
|---|---|---|---|
| Chain-of-Thought Prompting | 2022 | [arXiv:2201.11903](https://arxiv.org/abs/2201.11903) | 让模型显式写出中间步骤；解释「为什么 CoT 有效」 |
| ReAct | 2022 | [arXiv:2210.03629](https://arxiv.org/abs/2210.03629) | Thought→Action→Observation 交错；现代 Agent 循环的理论基石，**必背** |
| Tree of Thoughts | 2023 | [arXiv:2305.10601](https://arxiv.org/abs/2305.10601) | 树状多路径 + 自我评估；理解「搜索式推理」的代价 |
| Reflexion | 2023 | [arXiv:2303.11366](https://arxiv.org/abs/2303.11366) | 语言式强化学习，不更新权重也能迭代改进；反思机制源头 |
| LATS | 2023 | [arXiv:2310.04406](https://arxiv.org/abs/2310.04406) | 把 MCTS 与 LLM Agent 结合 |
| Toolformer | 2023 | [arXiv:2302.04761](https://arxiv.org/abs/2302.04761) | 模型自监督学会何时调 API；说明工具使用是可训练能力 |
| Voyager | 2023 | [arXiv:2305.16291](https://arxiv.org/abs/2305.16291) | 技能库累积 + 自动课程；今天 Skills / 技能复用的雏形 |
| Generative Agents | 2023 | [arXiv:2304.03442](https://arxiv.org/abs/2304.03442) | 记忆流 + 反思 + 规划，记忆系统设计的经典参照 |
| MemGPT | 2023 | [arXiv:2310.06825](https://arxiv.org/abs/2310.06825) | 把上下文当「内存」、外部存储当「磁盘」做分页；理解记忆分层 |

### 多智能体

| 论文 | 年份 | 链接 | 一句话 |
|---|---|---|---|
| CAMEL | 2023 | [arXiv:2303.17760](https://arxiv.org/abs/2303.17760) | 角色扮演式多 Agent 对话范式 |
| MetaGPT | 2023 | [arXiv:2308.00352](https://arxiv.org/abs/2308.00352) | SOP 驱动的「软件公司」多角色协作，结构化交付物优于自由聊天 |
| ChatDev | 2023 | [arXiv:2307.07924](https://arxiv.org/abs/2307.07924) | 多 Agent 软件开发流水线 |

### RAG

| 论文 | 年份 | 链接 | 一句话 |
|---|---|---|---|
| RAG（原始） | 2020 | [arXiv:2005.11401](https://arxiv.org/abs/2005.11401) | 参数化 + 非参数化记忆结合的起点 |
| Self-RAG | 2023 | [arXiv:2310.11511](https://arxiv.org/abs/2310.11511) | 模型自己决定要不要检索、检索结果是否可用 |
| Corrective RAG (CRAG) | 2024 | [arXiv:2401.15884](https://arxiv.org/abs/2401.15884) | 检索质量自检 + 回退到 Web 搜索 |
| HyDE / RAPTOR / GraphRAG | — | 见 [05-rag](05-rag/README.md) | 假设文档嵌入、树状聚合、图谱增强 |

### 评估与安全基准

| 基准 | 年份 | 链接 | 考什么 |
|---|---|---|---|
| SWE-bench | 2023 | [arXiv:2310.06770](https://arxiv.org/abs/2310.06770) · [榜单](https://www.swebench.com/) | 真实 GitHub issue，用测试通过与否判分（结果状态而非文本） |
| WebArena | 2023 | [arXiv:2307.12856](https://arxiv.org/abs/2307.12856) | 自托管网站上的真实浏览任务 |
| GAIA | 2023 | [arXiv:2311.12983](https://arxiv.org/abs/2311.12983) | 多步推理 + 工具使用的通用助手任务 |
| τ-bench / τ²-bench | 2024 | [arXiv:2406.12045](https://arxiv.org/abs/2406.12045) | 模拟用户 + 领域策略，提出 `pass^k` 可靠性指标 |
| OSWorld | 2024 | [arXiv:2404.07972](https://arxiv.org/abs/2404.07972) | 真实桌面 / 跨应用操作 |
| AgentDojo | 2024 | [arXiv:2406.13352](https://arxiv.org/abs/2406.13352) | 间接提示词注入攻防 |

### LLM 底座

| 论文 | 链接 | 面试考点 |
|---|---|---|
| Attention Is All You Need (2017) | [arXiv:1706.03762](https://arxiv.org/abs/1706.03762) | QKV、缩放、多头、位置编码 |
| LoRA (2021) | [arXiv:2106.09685](https://arxiv.org/abs/2106.09685) | 低秩假设、r / alpha、可插拔 |
| QLoRA (2023) | [arXiv:2305.14314](https://arxiv.org/abs/2305.14314) | 4-bit NF4 + LoRA |
| InstructGPT / RLHF (2022) | [arXiv:2203.02155](https://arxiv.org/abs/2203.02155) | SFT → RM → PPO 三阶段 |
| DPO (2023) | [arXiv:2305.18290](https://arxiv.org/abs/2305.18290) | 绕过奖励模型直接优化偏好对 |

---

## 三、协议与规范

| 名称 | 链接 | 要点 |
|---|---|---|
| Model Context Protocol | [官方文档](https://modelcontextprotocol.io) · [规范](https://modelcontextprotocol.io/specification/latest) · [SDK 仓库](https://github.com/modelcontextprotocol) | Host / Client / Server；tools、resources、prompts；stdio 与 Streamable HTTP；**agent ↔ 工具** |
| Agent2Agent (A2A) | [官方文档](https://a2a-protocol.org) · [GitHub](https://github.com/a2aproject/A2A) | Agent Card 能力发现、任务生命周期、JSON-RPC + SSE；**agent ↔ agent**；现由 Linux Foundation 维护 |
| Agent Skills 开放标准 | [Anthropic 文档](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills) | `SKILL.md` + 渐进式披露；程序性记忆 |
| OpenTelemetry GenAI 语义约定 | [文档](https://opentelemetry.io/docs/specs/semconv/gen-ai/) | trace / span 标准化，做可观测性时的通用语言 |
| OWASP Top 10 for LLM / Agentic Applications | [genai.owasp.org](https://genai.owasp.org/) | 提示词注入、过度代理、供应链、数据泄露等风险清单 |

> **一句话记牢**：MCP 管「Agent 连工具和数据」，A2A 管「Agent 找 Agent」，两者分层且互补，不是竞争关系。

---

## 四、框架与源码（读源码比读 API 文档有用）

| 项目 | 链接 | 适合学什么 |
|---|---|---|
| LangGraph | [github.com/langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | 显式图 / 状态机、checkpoint、可恢复执行、human-in-the-loop |
| OpenAI Agents SDK | [github.com/openai/openai-agents-python](https://github.com/openai/openai-agents-python) | 极简 handoff / guardrail / tracing 抽象，代码量小适合通读 |
| Microsoft AutoGen | [github.com/microsoft/autogen](https://github.com/microsoft/autogen) | 对话驱动的多 Agent 协作 |
| CrewAI | [github.com/crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | 角色 / 任务 / 流程的声明式编排 |
| LlamaIndex | [github.com/run-llama/llama_index](https://github.com/run-llama/llama_index) | 索引、检索器、Agentic RAG |
| smolagents | [github.com/huggingface/smolagents](https://github.com/huggingface/smolagents) | CodeAgent：让模型写 Python 而不是输出 JSON 工具调用 |
| Claude Agent SDK | [官方文档](https://docs.anthropic.com/en/api/agent-sdk/overview) | 生产级 Harness 的参考实现 |

---

## 五、开源课程与实战仓库

| 项目 | 链接 | 定位 |
|---|---|---|
| Microsoft AI Agents for Beginners | [github.com/microsoft/ai-agents-for-beginners](https://github.com/microsoft/ai-agents-for-beginners) | 12 课体系化入门，含简体中文 |
| Datawhale hello-agents | [github.com/datawhalechina/hello-agents](https://github.com/datawhalechina/hello-agents) | **中文、脱离框架手搓 ReAct / Plan-and-Solve / Reflection**，面试深挖底层首选 |
| Hugging Face Agents Course | [github.com/huggingface/agents-course](https://github.com/huggingface/agents-course) | 轻量 Code Agent，云端可跑，有结业证书 |
| NirDiamant GenAI_Agents | [github.com/NirDiamant/GenAI_Agents](https://github.com/NirDiamant/GenAI_Agents) | 45+ Notebook，从基础到多智能体全覆盖 |
| agents-towards-production | [github.com/NirDiamant/agents-towards-production](https://github.com/NirDiamant/agents-towards-production) | 生产级：可观测、权限、监控、评估、成本 |
| 500 AI Agents Projects | [github.com/ashishpatel26/500-AI-Agents-Projects](https://github.com/ashishpatel26/500-AI-Agents-Projects) | 按行业分类的练手项目库，做作品集用 |
| Prompt Engineering Guide | [promptingguide.ai](https://www.promptingguide.ai/) | 提示技术速查，含中文 |

---

## 六、中文面试题与面经（用来查漏，不要当教材）

- [面灵 AI · AI Agent 面试题 155 道](https://www.mianlingai.com/topics/ai-agent-interview-questions-2026/) — 按主题分类、标注出题公司，2026 新考点较全
- [面试鸭 · AI Agent 智能体面试题](https://www.mianshiya.com/?category=ai) — 含架构图解析
- [AI Agent 开发工程师面试准备完整指南](https://www.cnblogs.com/offergod/p/23332560/ai-agent-engineer-interview-guide) — 40 道核心题 + 项目案例组织方式

---

## 七、建议阅读顺序

```
第 1 周  必读 ① ② ④ + Lilian Weng 综述          → 建立词汇表与边界感
第 2 周  ReAct / CoT / Reflexion / ToT 论文       → 理解循环从哪来
第 3 周  必读 ⑤ + MemGPT + 工具设计文章           → 上下文与工具
第 4 周  MCP / A2A 规范 + 各框架 quickstart       → 协议与生态
第 5 周  SWE-bench / τ-bench / AgentDojo + 评估文章 → 评估与安全
第 6 周  中文面经查漏 + 自己写一遍所有最小实现     → 输出与自测
```

> 注意：本清单里的链接以各项目官方仓库 README 为准，开源项目会持续更新；论文编号已做可访问性核对。
> 读任何二手解读前，先确认它引用的是上面哪一篇一手资料。
