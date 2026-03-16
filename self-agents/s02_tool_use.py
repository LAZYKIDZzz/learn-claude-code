#!/usr/bin/env python3
"""
s02_tool_use.py - 工具系统

从 s01 的 agent 循环没有改变，我们只是添加了更多工具到数组中，
并使用一个分发器（dispatcher）来路由调用。

    +----------+      +-------+      +------------------+
    |   用户   | ---> |  LLM  | ---> | 工具分发器       |
    |   提示   |      |       |      | {                |
    +----------+      +---+---+      |   bash: run_bash |
                          ^          |   read: run_read |
                          |          |   write: run_wr  |
                          +----------+   edit: run_edit |
                          工具结果   | }                |
                                     +------------------+

关键洞察："循环完全没变，我只是添加了工具。"
"""

import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)
MODEL = os.getenv("MODEL_ID", "gpt-4")

# 工作目录：所有文件操作都限制在这个目录下
WORKDIR = Path.cwd()

SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. Act, don't explain."


def safe_path(p: str) -> Path:
    """
    安全路径检查：防止路径遍历攻击

    确保所有文件操作都在工作目录内，防止访问 /etc/passwd 等敏感文件

    参数:
        p: 用户提供的路径

    返回:
        解析后的安全路径

    异常:
        ValueError: 如果路径试图逃离工作目录
    """
    path = (WORKDIR / p).resolve()  # 解析为绝对路径
    if not path.is_relative_to(WORKDIR):  # 检查是否在工作目录内
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    """执行 bash 命令"""
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
    """
    读取文件内容

    参数:
        path: 文件路径
        limit: 可选，限制读取的行数

    返回:
        文件内容（如果设置了 limit，会截断并显示省略信息）
    """
    try:
        text = safe_path(path).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            # 如果超过限制，截断并添加提示
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)[:50000]  # 限制总长度
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    """
    写入文件

    参数:
        path: 文件路径
        content: 要写入的内容

    返回:
        成功消息或错误信息
    """
    try:
        fp = safe_path(path)
        # 自动创建父目录
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    """
    编辑文件：精确替换文本

    这是一个简单但强大的编辑模式：
    - 找到 old_text 的第一次出现
    - 替换为 new_text
    - 如果找不到 old_text，返回错误

    参数:
        path: 文件路径
        old_text: 要替换的文本（必须精确匹配）
        new_text: 新文本

    返回:
        成功消息或错误信息
    """
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        # 只替换第一次出现（replace 的第三个参数是替换次数）
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


# -- 工具分发器：{工具名: 处理函数} --
# 使用 lambda 函数将工具参数映射到实际的函数调用
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
}

# 工具定义：描述每个工具的功能和参数
TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
]

def build_openai_tools(tools: list) -> list:
    """将通用工具定义转换为 OpenAI function calling 格式"""
    return [{
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        }
    } for tool in tools]


def parse_openai_arguments(raw: str) -> dict:
    """
    解析 OpenAI 工具参数（注意：arguments 是 JSON 字符串）

    返回解析后的 dict；如果解析失败，返回包含错误信息的占位 dict。
    """
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return {"_parse_error": str(e), "_raw": raw}


def agent_loop_openai(messages: list):
    """OpenAI 的 agent 循环"""
    # 转换工具定义为 OpenAI 格式（function calling）
    openai_tools = build_openai_tools(TOOLS)

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

        for tool_call in tool_calls:
            args = parse_openai_arguments(tool_call.function.arguments)
            handler = TOOL_HANDLERS.get(tool_call.function.name)
            if "_parse_error" in args:
                output = f"Error: Invalid tool arguments for {tool_call.function.name}: {args['_raw']}"
            else:
                output = handler(**args) if handler else f"Unknown tool: {tool_call.function.name}"
            print(f"> {tool_call.function.name}: {output[:200]}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(output)
            })


agent_loop = agent_loop_openai


if __name__ == "__main__":
    history = []
    print("工具系统示例 - 现在有 4 个工具可用：bash, read_file, write_file, edit_file")
    print("试试：'创建一个 test.py 文件，写入 print(\"hello\")'")
    print()

    while True:
        try:
            query = input("\033[36ms02 >> \033[0m")
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
