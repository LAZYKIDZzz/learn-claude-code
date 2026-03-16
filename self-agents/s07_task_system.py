#!/usr/bin/env python3
"""
s07_task_system.py - 任务系统（Task System）

任务以 JSON 文件形式持久化到 .tasks/ 目录，可以在上下文压缩后继续存在。
每个任务都有依赖关系图（blockedBy/blocks）。

    .tasks/
      task_1.json  {"id":1, "subject":"...", "status":"completed", ...}
      task_2.json  {"id":2, "blockedBy":[1], "status":"pending", ...}
      task_3.json  {"id":3, "blockedBy":[2], "blocks":[], ...}

    依赖关系解析：
    +----------+     +----------+     +----------+
    | 任务 1   | --> | 任务 2   | --> | 任务 3   |
    | 已完成   |     | 被阻塞   |     | 被阻塞   |
    +----------+     +----------+     +----------+
         |                ^
         +--- 完成任务 1 会从任务 2 的 blockedBy 中移除它

关键洞察："状态在压缩后仍然存在 —— 因为它在对话之外。"
"""

import json
import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

# 根据环境变量选择 AI 提供商
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")

if AI_PROVIDER == "anthropic":
    from anthropic import Anthropic
    if os.getenv("ANTHROPIC_BASE_URL"):
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
    client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
    MODEL = os.environ.get("MODEL_ID", "claude-3-5-sonnet-20241022")
elif AI_PROVIDER == "openai":
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL")
    )
    MODEL = os.getenv("MODEL_ID", "gpt-4")
else:
    raise ValueError(f"不支持的 AI_PROVIDER: {AI_PROVIDER}")

WORKDIR = Path.cwd()
TASKS_DIR = WORKDIR / ".tasks"

SYSTEM = f"You are a coding agent at {WORKDIR}. Use task tools to plan and track work."


# -- TaskManager: 带依赖关系图的 CRUD，持久化为 JSON 文件 --
class TaskManager:
    """
    任务管理器：管理任务的创建、读取、更新和依赖关系

    任务以 JSON 文件形式存储在 .tasks/ 目录中，每个任务一个文件。
    支持任务依赖关系：一个任务可以被其他任务阻塞（blockedBy），
    也可以阻塞其他任务（blocks）。
    """

    def __init__(self, tasks_dir: Path):
        """
        初始化任务管理器

        参数:
            tasks_dir: 任务文件存储目录
        """
        self.dir = tasks_dir
        self.dir.mkdir(exist_ok=True)  # 确保目录存在
        self._next_id = self._max_id() + 1  # 计算下一个任务 ID

    def _max_id(self) -> int:
        """
        获取当前最大的任务 ID

        返回:
            最大任务 ID，如果没有任务则返回 0
        """
        # 从所有 task_*.json 文件名中提取 ID
        ids = [int(f.stem.split("_")[1]) for f in self.dir.glob("task_*.json")]
        return max(ids) if ids else 0

    def _load(self, task_id: int) -> dict:
        """
        从磁盘加载任务

        参数:
            task_id: 任务 ID

        返回:
            任务字典
        """
        path = self.dir / f"task_{task_id}.json"
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        return json.loads(path.read_text())

    def _save(self, task: dict):
        """
        将任务保存到磁盘

        参数:
            task: 任务字典
        """
        path = self.dir / f"task_{task['id']}.json"
        path.write_text(json.dumps(task, indent=2))

    def create(self, subject: str, description: str = "") -> str:
        """
        创建新任务

        参数:
            subject: 任务主题
            description: 任务描述（可选）

        返回:
            任务的 JSON 字符串
        """
        task = {
            "id": self._next_id,
            "subject": subject,
            "description": description,
            "status": "pending",      # 初始状态为待处理
            "blockedBy": [],          # 被哪些任务阻塞
            "blocks": [],             # 阻塞哪些任务
            "owner": "",              # 任务负责人
        }
        self._save(task)
        self._next_id += 1
        return json.dumps(task, indent=2)

    def get(self, task_id: int) -> str:
        """
        获取任务详情

        参数:
            task_id: 任务 ID

        返回:
            任务的 JSON 字符串
        """
        return json.dumps(self._load(task_id), indent=2)

    def update(self, task_id: int, status: str = None,
               add_blocked_by: list = None, add_blocks: list = None) -> str:
        """
        更新任务状态或依赖关系

        参数:
            task_id: 任务 ID
            status: 新状态（pending/in_progress/completed）
            add_blocked_by: 添加阻塞此任务的任务 ID 列表
            add_blocks: 添加此任务阻塞的任务 ID 列表

        返回:
            更新后任务的 JSON 字符串
        """
        task = self._load(task_id)

        # 更新状态
        if status:
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Invalid status: {status}")
            task["status"] = status

            # 当任务完成时，从所有其他任务的 blockedBy 中移除它
            if status == "completed":
                self._clear_dependency(task_id)

        # 添加阻塞此任务的任务
        if add_blocked_by:
            task["blockedBy"] = list(set(task["blockedBy"] + add_blocked_by))

        # 添加此任务阻塞的任务（双向更新）
        if add_blocks:
            task["blocks"] = list(set(task["blocks"] + add_blocks))
            # 双向关系：同时更新被阻塞任务的 blockedBy 列表
            for blocked_id in add_blocks:
                try:
                    blocked = self._load(blocked_id)
                    if task_id not in blocked["blockedBy"]:
                        blocked["blockedBy"].append(task_id)
                        self._save(blocked)
                except ValueError:
                    pass  # 如果任务不存在，忽略

        self._save(task)
        return json.dumps(task, indent=2)

    def _clear_dependency(self, completed_id: int):
        """
        从所有其他任务的 blockedBy 列表中移除已完成的任务

        参数:
            completed_id: 已完成的任务 ID
        """
        for f in self.dir.glob("task_*.json"):
            task = json.loads(f.read_text())
            if completed_id in task.get("blockedBy", []):
                task["blockedBy"].remove(completed_id)
                self._save(task)

    def list_all(self) -> str:
        """
        列出所有任务及其状态

        返回:
            任务列表的文本表示
        """
        tasks = []
        for f in sorted(self.dir.glob("task_*.json")):
            tasks.append(json.loads(f.read_text()))

        if not tasks:
            return "No tasks."

        lines = []
        for t in tasks:
            # 状态标记：[ ] 待处理，[>] 进行中，[x] 已完成
            marker = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[x]"
            }.get(t["status"], "[?]")

            # 显示阻塞信息
            blocked = f" (blocked by: {t['blockedBy']})" if t.get("blockedBy") else ""
            lines.append(f"{marker} #{t['id']}: {t['subject']}{blocked}")

        return "\n".join(lines)


# 创建全局任务管理器实例
TASKS = TaskManager(TASKS_DIR)


# -- 基础工具实现 --
def safe_path(p: str) -> Path:
    """
    安全路径检查：防止路径遍历攻击

    参数:
        p: 相对路径

    返回:
        解析后的绝对路径
    """
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    """
    执行 bash 命令

    参数:
        command: 要执行的命令

    返回:
        命令输出
    """
    # 危险命令黑名单
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"

    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=WORKDIR,
            capture_output=True,
            text=True,
            timeout=120
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, limit: int = None) -> str:
    """
    读取文件内容

    参数:
        path: 文件路径
        limit: 最大行数限制

    返回:
        文件内容
    """
    try:
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    """
    写入文件

    参数:
        path: 文件路径
        content: 文件内容

    返回:
        写入结果
    """
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    """
    编辑文件：替换文本

    参数:
        path: 文件路径
        old_text: 要替换的文本
        new_text: 新文本

    返回:
        编辑结果
    """
    try:
        fp = safe_path(path)
        c = fp.read_text()
        if old_text not in c:
            return f"Error: Text not found in {path}"
        fp.write_text(c.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


# 工具处理器映射：工具名 -> 处理函数
TOOL_HANDLERS = {
    "bash":        lambda **kw: run_bash(kw["command"]),
    "read_file":   lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file":  lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":   lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "task_create": lambda **kw: TASKS.create(kw["subject"], kw.get("description", "")),
    "task_update": lambda **kw: TASKS.update(kw["task_id"], kw.get("status"), kw.get("addBlockedBy"), kw.get("addBlocks")),
    "task_list":   lambda **kw: TASKS.list_all(),
    "task_get":    lambda **kw: TASKS.get(kw["task_id"]),
}

# 工具定义：描述工具的功能和参数
TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "task_create", "description": "Create a new task.",
     "input_schema": {"type": "object", "properties": {"subject": {"type": "string"}, "description": {"type": "string"}}, "required": ["subject"]}},
    {"name": "task_update", "description": "Update a task's status or dependencies.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}, "addBlockedBy": {"type": "array", "items": {"type": "integer"}}, "addBlocks": {"type": "array", "items": {"type": "integer"}}}, "required": ["task_id"]}},
    {"name": "task_list", "description": "List all tasks with status summary.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "task_get", "description": "Get full details of a task by ID.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]}},
]


def agent_loop_anthropic(messages: list):
    """Anthropic 的 agent 循环"""
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})

        # 如果不是工具调用，结束循环
        if response.stop_reason != "tool_use":
            return

        # 处理工具调用
        results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                try:
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    output = f"Error: {e}"

                print(f"> {block.name}: {str(output)[:200]}")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})

        messages.append({"role": "user", "content": results})


def agent_loop_openai(messages: list):
    """OpenAI 的 agent 循环"""
    # 转换工具格式为 OpenAI 格式
    openai_tools = [{
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        }
    } for tool in TOOLS]

    def parse_openai_arguments(raw: str) -> dict:
        """解析 OpenAI 工具参数（arguments 是 JSON 字符串）"""
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            return {"_parse_error": str(e), "_raw": raw}

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM}] + messages,
            tools=openai_tools,
            max_tokens=8000,
        )

        message = response.choices[0].message
        assistant_msg = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            assistant_msg["tool_calls"] = message.tool_calls
        messages.append(assistant_msg)

        # 如果没有工具调用，结束循环
        tool_calls = message.tool_calls or []
        if not tool_calls:
            return

        # 处理工具调用
        for tool_call in tool_calls:
            args = parse_openai_arguments(tool_call.function.arguments)

            handler = TOOL_HANDLERS.get(tool_call.function.name)
            try:
                if "_parse_error" in args:
                    output = f"Error: Invalid tool arguments for {tool_call.function.name}: {args['_raw']}"
                else:
                    output = handler(**args) if handler else f"Unknown tool: {tool_call.function.name}"
            except Exception as e:
                output = f"Error: {e}"

            print(f"> {tool_call.function.name}: {str(output)[:200]}")
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(output)
            })


# 根据提供商选择对应的循环函数
agent_loop = agent_loop_anthropic if AI_PROVIDER == "anthropic" else agent_loop_openai


if __name__ == "__main__":
    """
    主程序：实现一个简单的交互式命令行界面
    """
    history = []
    print("任务系统示例 - 任务持久化到 .tasks/ 目录")
    print("试试：'创建三个任务：设计、开发、测试，并设置依赖关系'")
    print()

    while True:
        try:
            # 读取用户输入（青色提示符）
            query = input("\033[36ms07 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            # Ctrl+D 或 Ctrl+C 退出
            break

        # 退出命令
        if query.strip().lower() in ("q", "exit", ""):
            break

        # 将用户输入添加到历史
        history.append({"role": "user", "content": query})

        # 运行 agent 循环
        agent_loop(history)

        # 提取并打印 AI 的文本响应
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        elif isinstance(response_content, str) and response_content.strip():
            print(response_content)
        print()
