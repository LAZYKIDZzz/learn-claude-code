# AI Agent 学习指南

这个目录包含了从零开始构建 AI Agent 的教学代码，每个文件都是一个独立可运行的示例，展示了 AI Agent 的核心概念和实现模式。

## 📚 学习路径

### 基础篇

#### [s01_agent_loop.py](s01_agent_loop.py) - Agent 循环（核心模式）
**核心概念**：AI Agent 的本质就是一个循环
```python
while stop_reason == "tool_use":
    response = LLM(messages, tools)  # 调用大模型
    execute tools                     # 执行工具
    append results                    # 追加结果
```

**学到什么**：
- Agent 的核心循环模式
- 如何将工具结果反馈给 LLM
- 支持 Anthropic 和 OpenAI 两种接口

**运行示例**：
```bash
# 使用 Anthropic
export AI_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your_key
export MODEL_ID=claude-3-5-sonnet-20241022
python self-agents/s01_agent_loop.py

# 使用 OpenAI
export AI_PROVIDER=openai
export OPENAI_API_KEY=your_key
export MODEL_ID=gpt-4
python self-agents/s01_agent_loop.py
```

**试试这些命令**：
- "列出当前目录的文件"
- "创建一个 hello.txt 文件，内容是 Hello World"
- "查看 hello.txt 的内容"

---

#### [s02_tool_use.py](s02_tool_use.py) - 工具系统
**核心概念**：Agent 循环不变，只是添加更多工具

**新增工具**：
- `bash` - 执行 shell 命令
- `read_file` - 读取文件内容
- `write_file` - 写入文件
- `edit_file` - 编辑文件（精确替换）

**学到什么**：
- 如何定义工具的 schema
- 工具分发器（dispatcher）模式
- 路径安全检查（防止访问工作目录外的文件）

**关键代码**：
```python
TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"]),
    "read_file": lambda **kw: run_read(kw["path"]),
    # ...
}
```

---

#### [s03_todo_write.py](s03_todo_write.py) - 任务追踪
**核心概念**：让 AI 自己追踪进度

**新增功能**：
- TodoManager：结构化的任务状态管理
- 任务状态：pending（待处理）、in_progress（进行中）、completed（已完成）
- 自动提醒：如果 AI 连续 3 轮没更新任务，系统会提醒它

**学到什么**：
- AI 可以管理自己的任务列表
- 如何通过提醒机制引导 AI 行为
- 结构化状态管理

**任务格式**：
```python
{
    "id": "1",
    "text": "创建配置文件",
    "status": "in_progress"
}
```

---

#### [s04_subagent.py](s04_subagent.py) - 子 Agent
**核心概念**：用新的上下文生成子 Agent，完成后只返回摘要

**架构**：
```
父 Agent (messages=[...])
    ↓ 派发任务
子 Agent (messages=[])  ← 全新的上下文
    ↓ 执行并总结
父 Agent ← 只收到摘要
```

**学到什么**：
- 上下文隔离的重要性
- 如何避免父 Agent 的上下文被污染
- 子 Agent 不能递归调用（防止无限嵌套）

**使用场景**：
- 探索代码库（不污染主上下文）
- 独立的研究任务
- 并行处理多个子任务

---

#### [s05_skill_loading.py](s05_skill_loading.py) - 技能系统
**核心概念**：两层技能注入，避免系统提示词膨胀

**两层架构**：
1. **Layer 1（轻量）**：系统提示词中只包含技能名称和简短描述（~100 tokens/技能）
2. **Layer 2（按需）**：AI 调用 `load_skill` 时才加载完整的技能内容

**技能文件结构**：
```
skills/
  pdf/
    SKILL.md          ← YAML frontmatter + 详细说明
  code-review/
    SKILL.md
```

**学到什么**：
- 如何避免系统提示词过长
- 按需加载的设计模式
- YAML frontmatter 解析

---

### 进阶篇

#### [s06_context_compact.py](s06_context_compact.py) - 上下文压缩
**核心概念**：三层压缩管道，让 Agent 可以永久运行

**三层压缩**：
1. **Layer 1: micro_compact**（每轮静默执行）
   - 保留最近 3 个工具结果
   - 旧结果替换为 `[Previous: used tool_name]`

2. **Layer 2: auto_compact**（超过 50000 tokens 时触发）
   - 保存完整对话到 `.transcripts/`
   - 让 LLM 总结对话
   - 用摘要替换所有消息

3. **Layer 3: compact tool**（AI 主动触发）
   - AI 可以调用 `compact` 工具手动压缩

**学到什么**：
- 如何让 Agent 突破上下文限制
- 战略性遗忘的重要性
- 对话持久化

---

#### [s07_task_system.py](s07_task_system.py) - 任务系统
**核心概念**：任务持久化为 JSON 文件，支持依赖图

**任务依赖**：
```
task_1 (completed) → task_2 (blocked) → task_3 (blocked)
```

**文件结构**：
```
.tasks/
  task_1.json  {"id":1, "status":"completed", ...}
  task_2.json  {"id":2, "blockedBy":[1], ...}
```

**学到什么**：
- 状态持久化（不依赖对话上下文）
- 任务依赖管理
- 双向依赖更新

---

#### [s08_background_tasks.py](s08_background_tasks.py) - 后台任务
**核心概念**：在后台线程运行命令，不阻塞 Agent

**架构**：
```
主线程                    后台线程
Agent 循环                任务执行
  ↓                        ↓
[LLM 调用] ← 通知队列 ← [完成]
```

**学到什么**：
- 异步执行模式
- 线程安全的通知队列
- "发射后不管"（fire and forget）模式

**使用场景**：
- 长时间运行的测试
- 构建和编译
- 数据处理任务

---

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install anthropic openai python-dotenv
```

### 2. 配置环境变量
创建 `.env` 文件：
```bash
# 选择 AI 提供商（anthropic 或 openai）
AI_PROVIDER=anthropic

# Anthropic 配置
ANTHROPIC_API_KEY=your_anthropic_key
MODEL_ID=claude-3-5-sonnet-20241022

# 或者 OpenAI 配置
# AI_PROVIDER=openai
# OPENAI_API_KEY=your_openai_key
# MODEL_ID=gpt-4

# 可选：自定义 base_url（用于代理）
# ANTHROPIC_BASE_URL=https://your-proxy.com
# OPENAI_BASE_URL=https://your-proxy.com
```

### 3. 运行示例
```bash
# 从最简单的开始
python self-agents/s01_agent_loop.py

# 尝试更多工具
python self-agents/s02_tool_use.py

# 体验任务追踪
python self-agents/s03_todo_write.py
```

---

## 💡 核心概念总结

### 1. Agent 循环
所有 Agent 的核心都是同一个循环：
```python
while model_wants_to_use_tools:
    response = call_llm(messages, tools)
    results = execute_tools(response.tool_calls)
    messages.append(results)
```

### 2. 工具即能力
Agent 的能力完全由它可以使用的工具决定：
- 文件操作 → 可以读写代码
- Shell 命令 → 可以运行测试
- 网络请求 → 可以查询 API
- 数据库 → 可以存储状态

### 3. 上下文管理
长期运行的 Agent 必须管理上下文：
- **压缩**：定期总结对话
- **持久化**：重要状态存到文件
- **隔离**：用子 Agent 处理独立任务

### 4. 状态外部化
不要把所有状态都放在对话中：
- 任务列表 → JSON 文件
- 技能库 → Markdown 文件
- 对话历史 → JSONL 文件

---

## 🎯 学习建议

### 对于初学者
1. **从 s01 开始**：理解核心循环
2. **动手修改**：改变系统提示词，看看 AI 行为如何变化
3. **添加工具**：尝试添加一个新工具（比如 `list_files`）
4. **观察日志**：看看 AI 如何决定调用哪个工具

### 对于进阶学习者
1. **组合模式**：尝试组合多个文件的功能
2. **优化性能**：减少不必要的 LLM 调用
3. **错误处理**：添加更健壮的错误处理
4. **安全加固**：增强命令过滤和权限控制

### 实践项目
- **代码审查 Agent**：读取代码，提供改进建议
- **测试生成 Agent**：分析代码，生成单元测试
- **文档生成 Agent**：扫描项目，生成 README
- **重构 Agent**：识别代码异味，提出重构方案

---

## 🔧 常见问题

### Q: Anthropic 和 OpenAI 有什么区别？
A: 主要是 API 格式不同：
- Anthropic：`messages.create()`, 工具结果用 `tool_result`
- OpenAI：`chat.completions.create()`, 工具结果用 `tool` role，参数是 JSON 字符串

### Q: 为什么需要子 Agent？
A: 防止主 Agent 的上下文被大量细节污染。比如探索一个大型代码库，子 Agent 可以读取几十个文件，但只返回一个摘要给父 Agent。

### Q: 如何调试 Agent？
A:
1. 打印每次 LLM 调用的输入输出
2. 记录工具调用和结果
3. 使用 `print()` 查看对话历史长度
4. 保存完整对话到文件

### Q: Agent 卡住了怎么办？
A: 常见原因：
1. 工具返回了太多数据（限制输出长度）
2. 陷入循环（添加最大轮次限制）
3. 等待用户输入（确保工具是非交互的）
4. OpenAI 工具参数解析失败（检查工具 schema 和 arguments 是否为合法 JSON）

---

## 📖 延伸阅读

- [Anthropic Tool Use 文档](https://docs.anthropic.com/claude/docs/tool-use)
- [OpenAI Function Calling 文档](https://platform.openai.com/docs/guides/function-calling)
- [ReAct: Reasoning and Acting](https://arxiv.org/abs/2210.03629)
- [Toolformer 论文](https://arxiv.org/abs/2302.04761)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

如果你：
- 发现了 bug
- 有改进建议
- 想添加新的示例
- 有学习心得想分享

都欢迎参与贡献！

---

## 📄 许可证

MIT License - 自由使用和修改

---

**Happy Coding! 🎉**

记住：最好的学习方式就是动手实践。不要只是阅读代码，运行它，修改它，打破它，然后修复它！
