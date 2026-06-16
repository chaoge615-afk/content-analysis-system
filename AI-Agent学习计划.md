# AI Agent 开发工程师 — 学习计划

> 基于当前项目（智能内容分析系统）的技能盘点，针对 Agent 工程师岗位需求制定
> 制定日期：2026-06-07

---

## 技能盘点：你已经有什么

### ✅ 已掌握（核心技能）

| 技能 | 项目体现 | 市场匹配度 |
|------|---------|-----------|
| Multi-Agent Pipeline 编排（自研） | Text-to-SQL 4-Agent 协作系统 | ⭐⭐⭐⭐⭐ |
| Router Agent 路由设计 | 意图分类 + 查询分发 + 结果融合 | ⭐⭐⭐⭐⭐ |
| 工具调用 / Function Calling | Agent 调用 SQL 生成、Schema 检索等工具 | ⭐⭐⭐⭐⭐ |
| RAG 混合检索 | BM25 + 向量语义 + rank-based 融合 | ⭐⭐⭐⭐⭐ |
| LangChain 框架 | RAG Agent 开发 | ⭐⭐⭐⭐ |
| Prompt 工程 | Few-shot + CoT 模板，意图分类 Prompt | ⭐⭐⭐⭐ |
| Hermes Skill 开发 | B站视频监控 → 转写 → 精炼完整工作流 | ⭐⭐⭐⭐ |
| 双 LLM 接入 | DeepSeek V4 Pro + MiniMax M2.7 | ⭐⭐⭐⭐ |
| Docker Compose 部署 | 7 服务编排，profiles 双环境 | ⭐⭐⭐ |
| 全栈开发 | FastAPI + React 18 + TypeScript | ⭐⭐⭐ |

### ❌ 需要补的（市场刚需）

| 技能 | 重要程度 | 说明 |
|------|---------|------|
| LangGraph | 🔴 必修 | Agent 工作流编排行业标准，替代/补充 Multi-Agent Pipeline |
| MCP 协议 | 🔴 必修 | Agent 工具调用的标准化协议，2026 年爆发 |
| Agent 记忆系统 | 🔴 必修 | 短期/长期/情景记忆设计，Agent 进阶核心 |
| Agent 可观测性 | 🟡 重要 | 监控、调试、评估 Agent 行为 |
| A2A 协议 | 🟡 重要 | Agent-to-Agent 通信标准（Google 主导） |
| Agent 安全与对齐 | 🟡 重要 | Guardrails、Human-in-the-Loop |
| 企业级 Agent 平台 | 🟢 加分 | Coze、Dify、百炼等平台开发经验 |
| Agent 测试与评估 | 🟢 加分 | Agent 行为的自动化测试与质量评估 |

---

## 第一阶段：强化 Agent 深度（1-6周）

> 目标：补齐 Agent 核心技能短板，能独立搭建 LangGraph + MCP 驱动的 Agent 系统

### 第 1-2 周：LangGraph

**为什么学**：Multi-Agent Pipeline 你已经会了，但 LangGraph 是 Agent 工作流编排的行业标准框架，大厂更认。它比 Multi-Agent Pipeline 更灵活，支持有状态的循环工作流，是高端 Agent 岗位的核心要求。

**学什么**：
- [ ] LangGraph 核心概念：State、Node、Edge、Conditional Edge
- [ ] 有状态 Agent 设计：Checkpoint 持久化、人机协同断点
- [ ] 子图（Subgraph）：将复杂 Agent 系统拆分为可组合的子图
- [ ] 流式输出：Streaming 事件（token/更新/自定义事件）
- [ ] 与 LangChain 的集成：Tool、Retriever、ChatModel 在 LangGraph 中的使用

**学完做什么**：
- [ ] 用 LangGraph 重构你现有的 Router Agent（替代 Multi-Agent Pipeline 的 Router 逻辑）
- [ ] 实现一个带 Human-in-the-Loop 审批节点的 Text-to-SQL Agent

**学习资源**：
- 官方文档：https://langchain-ai.github.io/langgraph/
- LangChain Academy 免费课程：https://academy.langchain.com/courses/intro-to-langgraph
- 实战参考：你的 content-analysis-system 项目

---

### 第 3-4 周：MCP 协议（Model Context Protocol）

**为什么学**：MCP 是 2026 年 Agent 工具调用的标准化协议，Anthropic 主导，已被各大 Agent 平台采纳。掌握 MCP 意味着你的 Agent 能接入任何标准化的工具/数据源，这是高端岗位的分水岭。

**学什么**：
- [ ] MCP 架构：Host → Client → Server 三层模型
- [ ] MCP Server 开发：用 Python SDK 开发自定义 MCP Server（Resource / Tool / Prompt）
- [ ] MCP Client 集成：在 Agent 中接入 MCP Server
- [ ] MCP 安全模型：Capability-based security、User consent
- [ ] 常见 MCP Server 生态：文件系统、数据库、API、浏览器等

**学完做什么**：
- [ ] 把你的 bilibili-monitor 封装为 MCP Server（暴露视频搜索、转写、精炼为 Tool）
- [ ] 把 RAG 检索系统封装为 MCP Server（暴露知识库查询为 Tool）
- [ ] 用 LangGraph Agent 通过 MCP 协议调用上述两个 Server，实现统一问答

**学习资源**：
- 官方规范：https://modelcontextprotocol.io/
- Python SDK：https://github.com/modelcontextprotocol/python-sdk
- Anthropic 文档：https://docs.anthropic.com/en/docs/build-with-claude/mcp

---

### 第 5-6 周：Agent 记忆系统

**为什么学**：记忆系统是 Agent 从"单次工具"进化为"持续协作伙伴"的关键。没有记忆的 Agent 每次对话都从零开始，有记忆的 Agent 能基于历史上下文做出更精准的决策。这是面试高频考点。

**学什么**：
- [ ] 短期记忆（Conversation Memory）：对话上下文窗口管理、滑动窗口策略
- [ ] 长期记忆（Long-term Memory）：向量数据库存储 + 语义检索、摘要压缩
- [ ] 情景记忆（Episodic Memory）：关键事件记录与回溯
- [ ] 反思机制（Reflection）：Agent 对自身行为的评估与改进
- [ ] 记忆管理策略：遗忘机制、记忆合并、优先级排序

**学完做什么**：
- [ ] 为你的 Router Agent 添加长期记忆：记住用户的查询偏好、常用 UP 主、历史查询模式
- [ ] 实现反思机制：Agent 在 SQL 生成失败后自动分析原因并调整 Prompt
- [ ] 用 ChromaDB 存储 Agent 记忆，支持语义检索历史对话

**学习资源**：
- LangChain Memory 模块文档
- Mem0（开源 Agent 记忆层）：https://github.com/mem0ai/mem0
- 论文参考：Reflexion（Agent 反思机制）

---

## 第二阶段：拓展 Agent 广度（7-12周）

> 目标：掌握企业级 Agent 开发的关键能力，能设计生产级 Agent 系统

### 第 7-8 周：Agent 可观测性与评估

**为什么学**：生产环境的 Agent 不是写完就完了，你需要知道它在干什么、干得好不好、哪里出了问题。可观测性是企业级 Agent 岗位的核心加分项。

**学什么**：
- [ ] LangSmith：Agent 调用链追踪、Token 消耗监控、延迟分析
- [ ] Agent 评估框架：设计评估指标（准确率、完成率、延迟、成本）
- [ ] 日志与告警：Agent 异常行为检测、自动告警机制
- [ ] A/B 测试：不同 Agent 策略/Prompt 的效果对比
- [ ] 成本优化：Token 消耗分析、缓存策略、小模型分流

**学完做什么**：
- [ ] 给你的智能内容分析系统接入 LangSmith 追踪
- [ ] 建立 Agent 评估数据集（100+ 测试用例），自动化评估 Router Agent 的路由准确率
- [ ] 实现成本监控仪表盘：每次查询的 Token 消耗、LLM 调用次数、响应延迟

---

### 第 9-10 周：A2A 协议 + 多 Agent 协作进阶

**为什么学**：A2A（Agent-to-Agent）是 Google 主导的跨 Agent 通信标准，解决不同框架开发的 Agent 之间互操作的问题。你的 Multi-Agent Pipeline Agent 和未来的 LangGraph Agent 需要能互相通信。

**学什么**：
- [ ] A2A 协议核心概念：Agent Card、Task、Message、Artifact
- [ ] A2A Server 开发：将你的 Agent 暴露为 A2A Server
- [ ] A2A Client 集成：从另一个 Agent 调用远程 Agent
- [ ] 多 Agent 协作模式：管道式、星形、网格、层级式
- [ ] 任务分配与负载均衡：动态路由、能力匹配

**学完做什么**：
- [ ] 将你的 Router Agent 和 Text-to-SQL Agent 通过 A2A 协议连接
- [ ] 设计一个跨框架协作系统：LangGraph Agent 通过 A2A 调用 Multi-Agent Pipeline Agent
- [ ] 实现 Agent 能力注册表：每个 Agent 声明自己的能力边界，Router 动态分发

---

### 第 11-12 周：Agent 安全与企业级实践

**为什么学**：企业部署 Agent 最大的顾虑就是安全——Agent 会不会执行危险操作？会不会泄露数据？掌握安全与治理能力是从"能开发 Agent"到"能设计企业级 Agent 系统"的关键跨越。

**学什么**：
- [ ] Guardrails：输入/输出过滤、敏感信息检测、行为边界设定
- [ ] Human-in-the-Loop：关键操作人工审批、自动/手动模式切换
- [ ] 权限管理：Agent 的 Tool 调用权限分级、数据访问控制
- [ ] 合规审计：Agent 操作日志、决策链路追溯
- [ ] 沙箱执行：Agent 代码执行的安全隔离

**学完做什么**：
- [ ] 为你的 Text-to-SQL Agent 添加 Guardrails：禁止 DELETE/UPDATE/DROP 等危险 SQL
- [ ] 实现 Human-in-the-Loop：SQL 执行前需人工确认（高风险操作）
- [ ] 建立完整的操作审计日志：记录每次 Agent 决策的完整链路

---

## 第三阶段：Agent 架构师进阶（13-20周）

> 目标：从"开发 Agent"升级为"设计 Agent 系统架构"

### 第 13-16 周：企业级 Agent 平台

**学什么**：
- [ ] Dify 平台：工作流编排、知识库管理、Agent 发布
- [ ] Coze（扣子）：Bot 开发、插件系统、多 Agent 协作
- [ ] 阿里百炼：Agent 开发、模型微调、企业级部署
- [ ] 各平台对比：优劣分析、适用场景、定制能力

**学完做什么**：
- [ ] 在 Dify 上搭建一个保险行业 Agent（智能核保问答）
- [ ] 在 Coze 上发布一个公开的 Bot，积累用户数据
- [ ] 对比分析：同一个场景分别用 LangGraph、Dify、Coze 实现，记录差异

### 第 17-20 周：综合项目 — Agent 平台

**最终项目：构建一个企业级 Agent 开发平台**

将 20 周所学整合为一个完整项目：

```
┌─────────────────────────────────────────────┐
│              Agent 开发平台                    │
├──────────────┬──────────────────────────────┤
│  Agent 市场   │ 多个预置 Agent（SQL/RAG/...）  │
│  工作流编排   │ LangGraph 可视化编辑器          │
│  工具管理     │ MCP Server 注册与发现           │
│  记忆系统     │ 共享记忆 + Agent 私有记忆        │
│  可观测性     │ LangSmith 集成 + 自定义仪表盘    │
│  安全治理     │ Guardrails + HITL + 审计日志    │
│  部署运维     │ Docker Compose 一键部署         │
└──────────────┴──────────────────────────────┘
```

这个项目将成为你面试时的杀手锏——它证明你不只是"用过 Multi-Agent Pipeline 写了个 Demo"，而是能**从零设计一个生产级 Agent 系统**。

---

## 学习资源汇总

### 文档与教程

| 资源 | 链接 | 说明 |
|------|------|------|
| LangGraph 官方文档 | https://langchain-ai.github.io/langgraph/ | 必读 |
| LangChain Academy | https://academy.langchain.com/ | 免费课程，质量高 |
| MCP 官方规范 | https://modelcontextprotocol.io/ | 必读 |
| MCP Python SDK | https://github.com/modelcontextprotocol/python-sdk | 实战参考 |
| A2A 协议 | https://google.github.io/A2A/ | Google 主导 |
| Mem0 | https://github.com/mem0ai/mem0 | Agent 记忆层 |
| LangSmith | https://smith.langchain.com/ | Agent 可观测性 |
| Dify 文档 | https://docs.dify.ai/ | 企业级平台 |

### 开源项目（值得研究）

| 项目 | 说明 |
|------|------|
| AutoGen（微软） | 多 Agent 对话框架 |
| Multi-Agent Pipeline | 你已经用了，深入研究源码 |
| OpenManus | 通用 Agent 框架 |
| MetaGPT | 软件开发多 Agent |
| camel-ai | 角色扮演多 Agent |

### 社区与信息源

| 来源 | 说明 |
|------|------|
| LangChain Discord | Agent 技术讨论 |
| r/LocalLLaMA | 开源模型 + Agent 实践 |
| Hugging Face 博客 | 前沿技术解读 |
| 你的 CSDN 博客 | 学习过程中持续输出文章，6100 粉丝是你的放大器 |

---

## 每周时间规划建议

> 假设每周可投入 15-20 小时（工作日每晚 2h + 周末集中）

| 日 | 时间 | 内容 |
|----|------|------|
| 周一 | 2h | 理论学习（文档/课程） |
| 周二 | 2h | 理论学习（文档/课程） |
| 周三 | 2h | 动手实验（小 Demo） |
| 周四 | 2h | 动手实验（集成到项目） |
| 周五 | 2h | 复盘 + 写 CSDN 博客 |
| 周六 | 4-5h | 集中开发（项目实战） |
| 周日 | 3-4h | 集中开发 + 下周规划 |

---

## 面试准备 Checklist

学完上述内容后，确保能回答以下问题：

### Agent 架构设计
- [ ] 如何设计一个支持 10 种工具调用的 Agent 系统？
- [ ] Multi-Agent Pipeline vs LangGraph 各自的优劣？什么场景用哪个？
- [ ] 多 Agent 系统的任务分配策略有哪些？

### MCP / A2A
- [ ] MCP 和传统 REST API 调用的区别是什么？
- [ ] 如何设计一个通用的 MCP Server？
- [ ] A2A 协议解决了什么问题？与 MCP 的关系是什么？

### 记忆系统
- [ ] Agent 的短期记忆和长期记忆分别怎么实现？
- [ ] 记忆太多怎么办？遗忘策略怎么设计？
- [ ] 反思机制的原理和实现方式？

### 生产化
- [ ] 如何监控 Agent 的行为？异常怎么检测？
- [ ] Agent 生成了错误结果怎么处理？容错机制怎么设计？
- [ ] 如何评估 Agent 系统的效果？指标怎么定？

### 你的项目
- [ ] 用 5 分钟讲清楚你的智能内容分析系统的架构
- [ ] Router Agent 的路由准确率是多少？怎么评估的？
- [ ] 遇到过什么工程挑战？怎么解决的？

---

## 里程碑

| 时间点 | 里程碑 | 产出 |
|--------|--------|------|
| 第 2 周末 | LangGraph 上手 | 重构 Router Agent 并发布到 GitHub |
| 第 4 周末 | MCP 实战 | 2 个 MCP Server + 统一问答 Agent |
| 第 6 周末 | 记忆系统 | Agent 长期记忆 + 反思机制 |
| 第 8 周末 | 可观测性 | LangSmith 集成 + 评估数据集 |
| 第 10 周末 | A2A 协作 | 跨框架多 Agent 系统 |
| 第 12 周末 | 安全治理 | Guardrails + HITL + 审计日志 |
| 第 16 周末 | 企业平台 | Dify/Coze 实战项目 |
| 第 20 周末 | 综合项目 | Agent 开发平台（面试杀手锏） |

> 每个里程碑都写 CSDN 博客总结，20 周 ≈ 10 篇技术文章，你的 6100 粉丝会持续增长
