# Self-Agents 文件索引

快速查找你需要的文件。

## 📖 文档文件

| 文件 | 大小 | 用途 | 适合人群 |
|------|------|------|----------|
| [README.md](README.md) | 9.1KB | 完整学习指南 | 所有人（必读） |
| [QUICKSTART.md](QUICKSTART.md) | 2.3KB | 5分钟快速开始 | 新手入门 |
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | 6.5KB | 项目总结 | 了解项目全貌 |
| [COMPARISON.md](COMPARISON.md) | 8.6KB | 原版vs增强版对比 | 想了解改进点 |
| [INDEX.md](INDEX.md) | 本文件 | 文件索引 | 快速查找 |

## 💻 代码文件

### 基础篇
| 文件 | 大小 | 难度 | 核心概念 | 运行命令 |
|------|------|------|----------|----------|
| [s01_agent_loop.py](s01_agent_loop.py) | 7.6KB | ⭐ | Agent 循环 | `python s01_agent_loop.py` |
| [s02_tool_use.py](s02_tool_use.py) | 9.2KB | ⭐⭐ | 工具系统 | `python s02_tool_use.py` |
| [s03_todo_write.py](s03_todo_write.py) | 12KB | ⭐⭐ | 任务追踪 | `python s03_todo_write.py` |
| [s04_subagent.py](s04_subagent.py) | 12KB | ⭐⭐⭐ | 子 Agent | `python s04_subagent.py` |
| [s05_skill_loading.py](s05_skill_loading.py) | 12KB | ⭐⭐⭐ | 技能系统 | `python s05_skill_loading.py` |

### 进阶篇
| 文件 | 大小 | 难度 | 核心概念 | 运行命令 |
|------|------|------|----------|----------|
| [s06_context_compact.py](s06_context_compact.py) | 15KB | ⭐⭐⭐ | 上下文压缩 | `python s06_context_compact.py` |
| [s07_task_system.py](s07_task_system.py) | 14KB | ⭐⭐⭐ | 任务系统 | `python s07_task_system.py` |
| [s08_background_tasks.py](s08_background_tasks.py) | 14KB | ⭐⭐⭐ | 后台任务 | `python s08_background_tasks.py` |

## 🔧 工具文件

| 文件 | 用途 | 运行命令 |
|------|------|----------|
| [test_setup.py](test_setup.py) | 环境配置测试 | `python test_setup.py` |
| [.env.example](.env.example) | 配置文件示例 | `cp .env.example .env` |

## 🎯 学习路径

### 第一天：基础入门
1. 阅读 [QUICKSTART.md](QUICKSTART.md)
2. 配置环境（`.env`）
3. 运行 `test_setup.py` 验证配置
4. 运行 `s01_agent_loop.py` 体验基础循环

### 第二天：工具系统
1. 阅读 [README.md](README.md) 的"工具系统"部分
2. 运行 `s02_tool_use.py`
3. 尝试修改代码，添加新工具

### 第三天：任务管理
1. 运行 `s03_todo_write.py`
2. 观察 AI 如何追踪进度
3. 理解提醒机制

### 第四天：进阶概念
1. 运行 `s04_subagent.py` 理解上下文隔离
2. 运行 `s05_skill_loading.py` 理解按需加载

### 第五天：上下文管理
1. 运行 `s06_context_compact.py` 理解上下文压缩
2. 运行 `s07_task_system.py` 理解任务持久化
3. 运行 `s08_background_tasks.py` 理解后台任务

### 第六天：深入理解
1. 阅读 [COMPARISON.md](COMPARISON.md) 理解改进点
2. 对比原版代码（`../agents/`）
3. 尝试实现自己的功能

## 📚 按需查找

### 我想...

#### 快速开始
→ [QUICKSTART.md](QUICKSTART.md)

#### 理解核心概念
→ [README.md](README.md) 的"核心概念总结"部分

#### 配置环境
→ [.env.example](.env.example) + [test_setup.py](test_setup.py)

#### 了解改进点
→ [COMPARISON.md](COMPARISON.md)

#### 学习 Agent 循环
→ [s01_agent_loop.py](s01_agent_loop.py)

#### 学习工具系统
→ [s02_tool_use.py](s02_tool_use.py)

#### 学习任务追踪
→ [s03_todo_write.py](s03_todo_write.py)

#### 学习子 Agent
→ [s04_subagent.py](s04_subagent.py)

#### 学习技能系统
→ [s05_skill_loading.py](s05_skill_loading.py)

#### 学习上下文压缩
→ [s06_context_compact.py](s06_context_compact.py)

#### 学习任务系统
→ [s07_task_system.py](s07_task_system.py)

#### 学习后台任务
→ [s08_background_tasks.py](s08_background_tasks.py)

#### 添加 OpenAI 支持
→ 所有 `.py` 文件都已支持，查看代码中的 `AI_PROVIDER` 部分

#### 调试问题
→ [README.md](README.md) 的"常见问题"部分

## 📊 统计信息

- **总文件数**: 13 个
- **代码文件**: 8 个（s01-s08）
- **文档文件**: 5 个
- **总代码行数**: ~2,800 行
- **总文档行数**: ~1,080 行
- **总大小**: ~120KB

## 🔗 相关链接

### 原版代码
- `../agents/` - 原版教学代码（s01-s12）

### 外部资源
- [Anthropic 文档](https://docs.anthropic.com/claude/docs/tool-use)
- [OpenAI 文档](https://platform.openai.com/docs/guides/function-calling)

## 💡 使用建议

1. **新手**: 按顺序阅读文档和代码
2. **有经验**: 直接看 [COMPARISON.md](COMPARISON.md) 了解改进点
3. **遇到问题**: 先运行 `test_setup.py` 检查环境
4. **想深入**: 对比原版代码理解设计思路

## 🎓 学习检查清单

- [ ] 阅读 QUICKSTART.md
- [ ] 配置 .env 文件
- [ ] 运行 test_setup.py 通过所有测试
- [ ] 运行 s01_agent_loop.py 理解核心循环
- [ ] 运行 s02_tool_use.py 理解工具系统
- [ ] 运行 s03_todo_write.py 理解任务追踪
- [ ] 运行 s04_subagent.py 理解上下文隔离
- [ ] 运行 s05_skill_loading.py 理解按需加载
- [ ] 运行 s06_context_compact.py 理解上下文压缩
- [ ] 运行 s07_task_system.py 理解任务持久化
- [ ] 运行 s08_background_tasks.py 理解后台任务
- [ ] 阅读 README.md 完整指南
- [ ] 尝试修改代码添加新功能
- [ ] 阅读 COMPARISON.md 理解改进点
- [ ] 对比原版代码深入理解

完成以上清单，你就掌握了 AI Agent 的核心概念！🎉

---

**最后更新**: 2026-03-16
**版本**: 1.0
