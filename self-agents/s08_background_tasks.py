#!/usr/bin/env python3
"""
s08_background_tasks.py - 后台任务（Background Tasks）

在后台线程中运行命令。通知队列会在每次 LLM 调用前被清空以传递结果。

    主线程                     后台线程
    +-----------------+        +-----------------+
    | agent 循环      |        | 任务执行        |
    | ...             |        | ...             |
    | [LLM 调用] <---+------- | enqueue(result) |
    |  ^清空队列      |        +-----------------+
    +-----------------+

    时间线：
    Agent ----[启动 A]----[启动 B]----[其他工作]----
                 |              |
                 v              v
              [A 运行]      [B 运行]        (并行)
                 |              |
                 +-- 通知队列 --> [结果注入]

关键洞察："发射后不管 —— agent 不会在命令运行时阻塞。"
"""

import json
import os
import subprocess
import threading
import uuid
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

SYSTEM = f"You are a coding agent at {WORKDIR}. Use background_run for long-running commands."


# -- BackgroundManager: 线程执行 + 通知队列 --
class BackgroundManager:
    """
    后台任务管理器：在后台线程中执行命令，通过通知队列传递结果

    核心功能：
    - 在后台线程中运行命令，不阻塞主线程
    - 维护任务状态（running/completed/timeout/error）
    - 通过通知队列向主线程传递完成的任务结果
    """

    def __init__(self):
        """初始化后台任务管理器"""
        self.tasks = {}  # task_id -> {status, result, command}
        self._notification_queue = []  # 已完成任务的结果队列
        self._lock = threading.Lock()  # 线程锁，保护共享数据

    def run(self, command: str) -> str:
        """
        启动后台线程，立即返回 task_id

        参数:
            command: 要执行的命令

        返回:
            任务启动确认消息
        """
        # 生成唯一的任务 ID（UUID 的前 8 位）
        task_id = str(uuid.uuid4())[:8]

        # 记录任务信息
        self.tasks[task_id] = {
            "status": "running",
            "result": None,
            "command": command
        }

        # 创建并启动后台线程（daemon=True 表示主线程退出时自动结束）
        thread = threading.Thread(
            target=self._execute,
            args=(task_id, command),
            daemon=True
        )
        thread.start()

        return f"Background task {task_id} started: {command[:80]}"

    def _execute(self, task_id: str, command: str):
        """
        线程目标函数：运行子进程，捕获输出，推送到队列

        参数:
            task_id: 任务 ID
            command: 要执行的命令
        """
        try:
            # 执行命令，超时时间为 300 秒（5 分钟）
            r = subprocess.run(
                command,
                shell=True,
                cwd=WORKDIR,
                capture_output=True,
                text=True,
                timeout=300
            )
            output = (r.stdout + r.stderr).strip()[:50000]
            status = "completed"
        except subprocess.TimeoutExpired:
            output = "Error: Timeout (300s)"
            status = "timeout"
        except Exception as e:
            output = f"Error: {e}"
            status = "error"

        # 更新任务状态
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["result"] = output or "(no output)"

        # 将完成通知推送到队列（线程安全）
        with self._lock:
            self._notification_queue.append({
                "task_id": task_id,
                "status": status,
                "command": command[:80],
                "result": (output or "(no output)")[:500],
            })

    def check(self, task_id: str = None) -> str:
        """
        检查一个任务的状态或列出所有任务

        参数:
            task_id: 任务 ID（可选，不提供则列出所有任务）

        返回:
            任务状态信息
        """
        if task_id:
            # 检查单个任务
            t = self.tasks.get(task_id)
            if not t:
                return f"Error: Unknown task {task_id}"
            return f"[{t['status']}] {t['command'][:60]}\n{t.get('result') or '(running)'}"

        # 列出所有任务
        lines = []
        for tid, t in self.tasks.items():
            lines.append(f"{tid}: [{t['status']}] {t['command'][:60]}")
        return "\n".join(lines) if lines else "No background tasks."

    def drain_notifications(self) -> list:
        """
        返回并清空所有待处理的完成通知

        返回:
            通知列表
        """
        with self._lock:
            notifs = list(self._notification_queue)
            self._notification_queue.clear()
        return notifs


# 创建全局后台任务管理器实例
BG = BackgroundManager()


# -- 工具实现 --
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
    执行 bash 命令（阻塞式）

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
    "bash":             lambda **kw: run_bash(kw["command"]),
    "read_file":        lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file":       lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":        lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "background_run":   lambda **kw: BG.run(kw["command"]),
    "check_background": lambda **kw: BG.check(kw.get("task_id")),
}

# 工具定义：描述工具的功能和参数
TOOLS = [
    {"name": "bash", "description": "Run a shell command (blocking).",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "background_run", "description": "Run command in background thread. Returns task_id immediately.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "check_background", "description": "Check background task status. Omit task_id to list all.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}}},
]


def agent_loop_anthropic(messages: list):
    """Anthropic 的 agent 循环（带后台任务通知）"""
    while True:
        # 在 LLM 调用前清空后台通知并注入为系统消息
        notifs = BG.drain_notifications()
        if notifs and messages:
            notif_text = "\n".join(
                f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs
            )
            messages.append({
                "role": "user",
                "content": f"<background-results>\n{notif_text}\n</background-results>"
            })
            messages.append({
                "role": "assistant",
                "content": "Noted background results."
            })

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
    """OpenAI 的 agent 循环（带后台任务通知）"""
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
        # 在 LLM 调用前清空后台通知并注入为系统消息
        notifs = BG.drain_notifications()
        if notifs and messages:
            notif_text = "\n".join(
                f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs
            )
            messages.append({
                "role": "user",
                "content": f"<background-results>\n{notif_text}\n</background-results>"
            })
            messages.append({
                "role": "assistant",
                "content": "Noted background results."
            })

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
    print("后台任务示例 - 使用 background_run 在后台运行长时间命令")
    print("试试：'在后台运行 sleep 5 && echo done'")
    print()

    while True:
        try:
            # 读取用户输入（青色提示符）
            query = input("\033[36ms08 >> \033[0m")
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
