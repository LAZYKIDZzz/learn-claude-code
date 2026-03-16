# 快速开始指南

这是一个 5 分钟快速上手指南，帮助你立即开始使用 AI Agent。

## 第一步：安装依赖

```bash
pip install anthropic openai python-dotenv
```

## 第二步：配置 API 密钥

复制示例配置文件：
```bash
cd self-agents
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API 密钥：

### 使用 Anthropic Claude
```bash
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxx
MODEL_ID=claude-3-5-sonnet-20241022
```

### 或使用 OpenAI GPT
```bash
AI_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxx
MODEL_ID=gpt-4
```

## 第三步：运行第一个 Agent

```bash
python s01_agent_loop.py
```

## 试试这些命令

### 基础操作
```
s01 >> 列出当前目录的文件
s01 >> 创建一个 hello.txt 文件，内容是 Hello World
s01 >> 查看 hello.txt 的内容
```

### 文件操作（s02）
```bash
python s02_tool_use.py
```

```
s02 >> 创建一个 Python 脚本 greet.py，定义一个函数打印问候语
s02 >> 读取 greet.py 的内容
s02 >> 在 greet.py 中添加一个 main 函数
```

### 任务追踪（s03）
```bash
python s03_todo_write.py
```

```
s03 >> 创建一个完整的 Python 项目，包含 main.py, utils.py, tests/ 目录和 README.md
```

观察 AI 如何：
1. 创建任务列表
2. 逐个标记为"进行中"
3. 完成后标记为"已完成"

### 子 Agent（s04）
```bash
python s04_subagent.py
```

```
s04 >> 探索这个项目的结构，告诉我有哪些主要的 Python 文件
```

观察子 Agent 如何在独立上下文中工作，只返回摘要。

## 常见问题

### Q: 提示 "API key not found"
A: 确保 `.env` 文件在当前目录，并且包含正确的 API 密钥。

### Q: 如何切换 AI 提供商？
A: 修改 `.env` 文件中的 `AI_PROVIDER` 为 `anthropic` 或 `openai`。

### Q: 如何退出程序？
A: 输入 `q`、`exit` 或按 `Ctrl+C`。

### Q: Agent 执行了危险命令怎么办？
A: 所有示例都内置了安全检查，会阻止 `rm -rf /`、`sudo` 等危险命令。

## 下一步

- 阅读 [README.md](README.md) 了解完整的学习路径
- 尝试修改代码，添加自己的工具
- 查看每个文件的详细注释，理解实现原理

## 需要帮助？

- 查看代码中的详细中文注释
- 阅读 README.md 中的核心概念
- 尝试不同的提示词，观察 AI 的行为

祝你学习愉快！🚀
