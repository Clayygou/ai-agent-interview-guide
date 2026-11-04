# 代码示例说明

**设计原则：零配置、零第三方依赖、可直接运行。**
所有示例只用 Python 标准库（3.9+），默认走 `llm_client.py` 里的 `ScriptedLLM`——
用预先写好的「模型输出脚本」驱动，把协议（模型输出 → 解析 → 执行 → 观察回填）暴露得清清楚楚。

```bash
python code/01_minimal_react_agent.py
python code/02_function_calling.py
python code/03_memory.py
python code/04_rag_pipeline.py
python code/05_mcp_server.py
python code/06_mcp_client.py
python code/07_multi_agent.py
python code/08_evaluator.py
python code/09_guardrails.py
```

> `05` 与 `06` 是一对：`06` 会自动把 `05` 作为子进程启动，走真实的 stdio JSON-RPC 握手。
> 单独跑 `05` 是演示模式；`python code/05_mcp_server.py --stdio` 才是协议模式。

---

## 文件对照表

| 文件 | 对应章节 | 你会看到什么 |
|---|---|---|
| `llm_client.py` | 共用 | 脚本化 Mock 模型 + 可选真实模型适配 + token 估算 |
| `01_minimal_react_agent.py` | [02 Agent 核心](../02-agent-core/README.md) | 完整 ReAct loop、错误回填自修正、三层停止条件、trace |
| `02_function_calling.py` | [03 工具与协议](../03-tools-and-protocols/README.md) | Schema 定义、参数校验、非法参数回填、有限重试与降级 |
| `03_memory.py` | [04 记忆与上下文](../04-memory-and-context/README.md) | 四层记忆、token 预算、压缩与不可丢清单、冲突与删除 |
| `04_rag_pipeline.py` | [05 RAG](../05-rag/README.md) | 结构切分、BM25+稠密、RRF、重排、编号引用、忠实度、注入扫描 |
| `05_mcp_server.py` | [03 工具与协议](../03-tools-and-protocols/README.md) | initialize / tools/list / tools/call / resources 的 JSON-RPC 实现 |
| `06_mcp_client.py` | [03 工具与协议](../03-tools-and-protocols/README.md) | 子进程 stdio 握手、能力发现、调用与错误处理 |
| `07_multi_agent.py` | [06 多智能体](../06-multi-agent/README.md) | 并行 fan-out、上下文与权限隔离、超时/失败回退、token 记账 |
| `08_evaluator.py` | [07 评估与可观测](../07-eval-and-observability/README.md) | 结果 vs 轨迹、`pass^k`、越权检测、CI 回归门禁 |
| `09_guardrails.py` | [08 安全与生产](../08-safety-and-production/README.md) | 工具分级、注入扫描、HITL checkpoint、幂等、预算熔断 |

---

## 接真实模型（可选）

设置环境变量后，所有 `get_client()` 会自动切换到 `OpenAICompatibleLLM`，
仍然**不需要安装 openai 包**（内部用标准库 `urllib` 调 `/chat/completions`）：

```bash
export LLM_API_KEY="sk-..."
export LLM_BASE_URL="https://api.openai.com/v1"     # 任何兼容服务均可
export LLM_MODEL="gpt-4o-mini"
python code/01_minimal_react_agent.py
```

Windows PowerShell：

```powershell
$env:LLM_API_KEY="sk-..."
$env:LLM_MODEL="gpt-4o-mini"
python code/01_minimal_react_agent.py
```

> 接真实模型时，`01` / `02` 的系统提示词已经写明了输出格式与工具用法；
> 其余示例刻意不依赖模型输出，方便离线观察机制。

---

## 教学替身说明（重要）

为了让代码零依赖可跑，三处用了简化实现。**链路结构完全一致，替换函数即可升级到生产版**：

| 位置 | 这里用的 | 生产里换成 |
|---|---|---|
| `04_rag_pipeline.py::vectorize` | 词哈希向量 | embedding 模型 + 向量数据库 |
| `04_rag_pipeline.py::rerank` | query 词重叠打分 | cross-encoder（BGE-Reranker / Cohere Rerank） |
| `04_rag_pipeline.py::extractive_answer` | 抽取式拼句 | LLM 生成 + 引用约束 |
| `07_multi_agent.py::plan` | 确定性计划 | 主 Agent 动态拆解 |
| `08_evaluator.py::mock_agent` | 模拟轨迹 | 你的真实 Agent |

不要把这些替身的**数值**当成结论；要学的是它们之间的**接口和数据流**。

---

## 建议的学习方式

1. 先原样跑一遍，读懂打印出来的每一步
2. 改一个参数（预算、fan-out、chunk 大小），看输出怎么变
3. **故意弄坏它**：写错工具名、删掉重复检测、塞入注入内容，观察失败方式
4. 合上代码，自己重写一遍最小版本 —— 能写出来才算掌握
5. 对照 [CHECKLIST.md](../CHECKLIST.md) 打勾，用 [INTERVIEW.md](../INTERVIEW.md) 的手撕代码题自测

> 没有项目经历时，把这 9 个示例跑通、改坏、修好，就是可以写进简历的项目：
> 你能讲清「为什么这样设计、出了什么故障、怎么定位、成本多少」。
