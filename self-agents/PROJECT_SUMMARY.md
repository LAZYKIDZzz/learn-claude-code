# Self-Agents 项目总结

## 📋 项目概述

本项目为 `agents/` 目录下的 AI Agent 教学代码创建了增强版本，包含：
1. **详细的中文注释** - 每个函数、类、关键代码块都有中文说明
2. **OpenAI 支持** - 扩展了原本只支持 Anthropic 的代码，现在同时支持 OpenAI
3. **完整的学习文档** - 从零开始的学习指南，适合新手小白

## 📁 文件结构

```
self-agents/
├── README.md              # 完整学习指南（核心文档）
├── QUICKSTART.md          # 5分钟快速开始
├── .env.example           # 环境变量配置示例
├── s01_agent_loop.py      # 01. Agent 循环（核心模式）
├── s02_tool_use.py        # 02. 工具系统
├── s03_todo_write.py      # 03. 任务追踪
├── s04_subagent.py        # 04. 子 Agent
└── s05_skill_loading.py   # 05. 技能系统
```

## ✨ 主要改进

### 1. 中文注释系统

每个文件都包含：
- **文件级注释**：解释整体架构和核心概念
- **函数级注释**：说明参数、返回值、功能
- **行内注释**：解释关键逻辑和设计决策
- **ASCII 图示**：可视化数据流和架构

示例：
```python
def run_bash(command: str) -> str:
    """
    执行 bash 命令的函数

    参数:
        command: 要执行的 shell 命令

    返回:
        命令的输出结果（stdout + stderr）
    """
    # 危险命令黑名单：防止执行破坏性操作
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    # ...
```

### 2. OpenAI 支持

所有文件都支持两种 AI 提供商：

**配置方式**：
```bash
# 使用 Anthropic
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key

# 或使用 OpenAI
AI_PROVIDER=openai
OPENAI_API_KEY=your_key
```

**实现方式**：
- 统一的工具处理器（TOOL_HANDLERS）
- 分离的 agent_loop 实现（anthropic/openai）
- 自动选择对应的循环函数

### 3. 学习文档

#### README.md（主文档）
- **学习路径**：从基础到进阶的完整路径
- **核心概念**：Agent 循环、工具系统、上下文管理
- **实践建议**：针对初学者和进阶学习者
- **常见问题**：调试技巧、问题排查

#### QUICKSTART.md（快速开始）
- 5 分钟上手指南
- 安装步骤
- 配置示例
- 试用命令

## 🎯 核心概念讲解

### 1. Agent 循环（s01）
```python
while stop_reason == "tool_use":
    response = LLM(messages, tools)  # 调用大模型
    execute tools                     # 执行工具
    append results                    # 追加结果
```

**学到什么**：
- AI Agent 的本质就是一个循环
- 工具结果反馈给 LLM 形成闭环
- 支持 Anthropic 和 OpenAI 两种接口

### 2. 工具系统（s02）
```python
TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"]),
    "read_file": lambda **kw: run_read(kw["path"]),
    # ...
}
```

**学到什么**：
- 工具分发器模式
- 路径安全检查
- 工具 schema 定义

### 3. 任务追踪（s03）
```python
[ ] #1: 创建配置文件
[>] #2: 编写主程序  ← 进行中
[x] #3: 添加测试

(1/3 completed)
```

**学到什么**：
- AI 自我管理进度
- 自动提醒机制
- 结构化状态管理

### 4. 子 Agent（s04）
```
父 Agent (messages=[...])
    ↓ 派发任务
子 Agent (messages=[])  ← 全新上下文
    ↓ 执行并总结
父 Agent ← 只收到摘要
```

**学到什么**：
- 上下文隔离
- 避免上下文污染
- 防止递归调用

### 5. 技能系统（s05）
```
Layer 1: 系统提示词（轻量）
  - pdf: Process PDF files
  - code-review: Review code

Layer 2: 按需加载（完整）
  load_skill("pdf") → 完整的 PDF 处理说明
```

**学到什么**：
- 避免系统提示词膨胀
- 按需加载设计模式
- YAML frontmatter 解析

## 🚀 使用方法

### 安装依赖
```bash
pip install anthropic openai python-dotenv
```

### 配置环境
```bash
cd self-agents
cp .env.example .env
# 编辑 .env 填入 API 密钥
```

### 运行示例
```bash
# 基础循环
python s01_agent_loop.py

# 工具系统
python s02_tool_use.py

# 任务追踪
python s03_todo_write.py

# 子 Agent
python s04_subagent.py

# 技能系统
python s05_skill_loading.py
```

## 💡 学习建议

### 对于初学者
1. **按顺序学习**：从 s01 到 s05，循序渐进
2. **动手实践**：运行代码，修改参数，观察变化
3. **阅读注释**：每个文件都有详细的中文注释
4. **尝试修改**：添加新工具、改变提示词

### 对于进阶学习者
1. **组合功能**：结合多个文件的特性
2. **优化性能**：减少 LLM 调用次数
3. **增强安全**：添加更多安全检查
4. **扩展功能**：实现更复杂的 Agent

## 🔍 与原版对比

| 特性 | 原版 (agents/) | 增强版 (self-agents/) |
|------|---------------|---------------------|
| 中文注释 | ❌ 无 | ✅ 详细的中文注释 |
| OpenAI 支持 | ❌ 仅 Anthropic | ✅ 支持两种提供商 |
| 学习文档 | ❌ 简单说明 | ✅ 完整学习指南 |
| 快速开始 | ❌ 无 | ✅ 5分钟上手指南 |
| 配置示例 | ❌ 无 | ✅ .env.example |
| 代码示例 | ✅ 有 | ✅ 更多提示 |

## 📚 文档亮点

### README.md 包含：
- 📖 完整的学习路径（基础篇 + 进阶篇）
- 💡 核心概念总结
- 🎯 学习建议（初学者 + 进阶）
- 🔧 常见问题解答
- 🚀 实践项目建议

### 每个代码文件包含：
- 📝 文件头部的架构图
- 💬 详细的中文注释
- 🎨 清晰的代码结构
- 🔍 关键洞察（Key Insight）
- 💻 使用示例提示

## 🎓 适用人群

1. **AI Agent 初学者**：从零开始学习 AI Agent 开发
2. **Python 开发者**：想了解 LLM 应用开发
3. **学生**：学习 AI 工程实践
4. **研究者**：理解 Agent 架构设计

## 🔗 相关资源

- [Anthropic Tool Use 文档](https://docs.anthropic.com/claude/docs/tool-use)
- [OpenAI Function Calling 文档](https://platform.openai.com/docs/guides/function-calling)
- [ReAct 论文](https://arxiv.org/abs/2210.03629)

## 📝 后续计划

可以继续添加的文件：
- `s06_context_compact.py` - 上下文压缩
- `s07_task_system.py` - 任务系统（持久化）
- `s08_background_tasks.py` - 后台任务
- 更多进阶示例...

## 🤝 贡献

欢迎：
- 报告问题
- 改进文档
- 添加示例
- 分享心得

## 📄 许可证

MIT License - 自由使用和修改

---

**创建时间**：2026-03-16
**版本**：1.0
**作者**：AI Agent 学习项目

Happy Coding! 🎉
