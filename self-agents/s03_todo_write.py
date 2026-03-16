#!/usr/bin/env python3
"""
s03_todo_write.py - 任务追踪（TodoWrite）

模型通过 TodoManager 追踪自己的进度。如果模型忘记更新，
会有一个提醒机制强制它保持更新。

    +----------+      +-------+      +---------+
    |   用户   | ---> |  LLM  | ---> | 工具    |
    |   提示   |      |       |      | + todo  |
    +----------+      +---+---+      +----+----+
                          ^               |
                          |   工具结果    |
                          +---------------+
                                |
                    +-----------+-----------+
                    | TodoManager 状态      |
                    | [ ] 任务 A            |
                    | [>] 任务 B <- 进行中  |
                    | [x] 任务 C            |
                    +-----------------------+
                                |
                    如果连续 3 轮没更新 todo:
                      注入 <reminder> 提醒

关键洞察："Agent 可以追踪自己的进度 -- 而且我能看到它。"
"""

import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

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

SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use the todo tool to plan multi-step tasks. Mark in_progress before starting, completed when done.
Prefer tools over prose."""


# -- TodoManager: LLM 写入的结构化状态 --
class TodoManager:
    """
    任务管理器：让 AI 追踪自己的进度

    任务状态：
    - pending: 待处理
    - in_progress: 进行中（同时只能有一个）
    - completed: 已完成
    """

    def __init__(self):
        self.items = []  # 任务列表

    def update(self, items: list) -> str:
        """
        更新任务列表

        验证规则：
        1. 最多 20 个任务
        2. 每个任务必须有 text
        3. 状态必须是 pending/in_progress/completed 之一
        4. 同时只能有一个任务是 in_progress

        参数:
            items: 任务列表，每个任务包含 id, text, status

        返回:
            渲染后的任务列表字符串
        """
        if len(items) > 20:
            raise ValueError("Max 20 todos allowed")

        validated = []
        in_progress_count = 0

        for i, item in enumerate(items):
            text = str(item.get("text", "")).strip()
            status = str(item.get("status", "pending")).lower()
            item_id = str(item.get("id", str(i + 1)))

            # 验证任务文本
            if not text:
                raise ValueError(f"Item {item_id}: text required")

            # 验证状态
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Item {item_id}: invalid status '{status}'")

            # 统计进行中的任务数量
            if status == "in_progress":
                in_progress_count += 1

            validated.append({"id": item_id, "text": text, "status": status})

        # 确保同时只有一个任务在进行中
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress at a time")

        self.items = validated
        return self.render()

    def render(self) -> str:
        """
        渲染任务列表为可读格式

        格式：
        [ ] #1: 任务描述（待处理）
        [>] #2: 任务描述（进行中）
        [x] #3: 任务描述（已完成）

        (2/3 completed)
        """
        if not self.items:
            return "No todos."

        lines = []
        for item in self.items:
            # 根据状态选择标记符号
            marker = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[x]"
            }[item["status"]]
            lines.append(f"{marker} #{item['id']}: {item['text']}")

        # 添加完成度统计
        done = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({done}/{len(self.items)} completed)")

        return "\n".join(lines)


# 全局 TodoManager 实例
TODO = TodoManager()


# -- 工具实现 --
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, limit: int = None) -> str:
    try:
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "todo":       lambda **kw: TODO.update(kw["items"]),  # 新增：todo 工具
}

TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "todo", "description": "Update task list. Track progress on multi-step tasks.",
     "input_schema": {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "text": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["id", "text", "status"]}}}, "required": ["items"]}},
]


# -- Agent 循环（带提醒注入） --
def agent_loop_anthropic(messages: list):
    """
    Anthropic 的 agent 循环，带自动提醒功能

    如果 AI 连续 3 轮没有更新 todo，会自动注入提醒消息
    """
    rounds_since_todo = 0  # 记录距离上次更新 todo 的轮数

    while True:
        # 提醒会在下面与工具结果一起注入
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return

        results = []
        used_todo = False  # 标记本轮是否使用了 todo 工具

        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                try:
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    output = f"Error: {e}"

                print(f"> {block.name}: {str(output)[:200]}")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})

                # 检查是否使用了 todo 工具
                if block.name == "todo":
                    used_todo = True

        # 更新计数器
        rounds_since_todo = 0 if used_todo else rounds_since_todo + 1

        # 如果连续 3 轮没更新，注入提醒
        if rounds_since_todo >= 3:
            results.insert(0, {"type": "text", "text": "<reminder>Update your todos.</reminder>"})

        messages.append({"role": "user", "content": results})


def agent_loop_openai(messages: list):
    """OpenAI 的 agent 循环，带自动提醒功能"""
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

    rounds_since_todo = 0

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

        tool_calls = message.tool_calls or []
        if not tool_calls:
            return

        used_todo = False
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

            if tool_call.function.name == "todo":
                used_todo = True

        rounds_since_todo = 0 if used_todo else rounds_since_todo + 1

        # OpenAI 的提醒注入方式
        if rounds_since_todo >= 3:
            messages.append({
                "role": "user",
                "content": "<reminder>Update your todos.</reminder>"
            })


agent_loop = agent_loop_anthropic if AI_PROVIDER == "anthropic" else agent_loop_openai


if __name__ == "__main__":
    history = []
    print("任务追踪示例 - AI 会自动追踪多步骤任务的进度")
    print("试试：'创建一个 Python 项目，包含 main.py, utils.py 和 README.md'")
    print("观察 AI 如何分解任务并追踪进度！")
    print()

    while True:
        try:
            query = input("\033[36ms03 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        elif isinstance(response_content, str) and response_content.strip():
            print(response_content)
        print()
