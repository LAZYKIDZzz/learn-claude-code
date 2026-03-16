#!/usr/bin/env python3
"""
s04_subagent.py - 子 Agent

生成一个带有全新 messages=[] 的子 Agent。子 Agent 在自己的上下文中工作，
共享文件系统，然后只返回摘要给父 Agent。

    父 Agent                        子 Agent
    +------------------+             +------------------+
    | messages=[...]   |             | messages=[]      |  <-- 全新
    |                  |  派发任务   |                  |
    | tool: task       | ---------->| while tool_use:  |
    |   prompt="..."   |            |   call tools     |
    |   description="" |            |   append results |
    |                  |  返回摘要   |                  |
    |   result = "..." | <--------- | return last text |
    +------------------+             +------------------+
              |
    父 Agent 的上下文保持干净。
    子 Agent 的上下文被丢弃。

关键洞察："进程隔离带来了上下文隔离，而且是免费的。"
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

WORKDIR = Path.cwd()

# 父 Agent 的系统提示词
SYSTEM = f"You are a coding agent at {WORKDIR}. Use the task tool to delegate exploration or subtasks."

# 子 Agent 的系统提示词
SUBAGENT_SYSTEM = f"You are a coding subagent at {WORKDIR}. Complete the given task, then summarize your findings."


# -- 父 Agent 和子 Agent 共享的工具实现 --
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
}

# 子 Agent 获得所有基础工具，但不包括 task（防止递归生成）
CHILD_TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
]


# -- 子 Agent：全新上下文，过滤的工具，只返回摘要 --
def run_subagent_openai(prompt: str) -> str:
    """运行 OpenAI 子 Agent"""
    openai_tools = [{
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        }
    } for tool in CHILD_TOOLS]

    def parse_openai_arguments(raw: str) -> dict:
        """解析 OpenAI 工具参数（arguments 是 JSON 字符串）"""
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            return {"_parse_error": str(e), "_raw": raw}

    sub_messages = [{"role": "user", "content": prompt}]

    for _ in range(30):
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SUBAGENT_SYSTEM}] + sub_messages,
            tools=openai_tools,
            max_tokens=8000,
        )

        message = response.choices[0].message
        assistant_msg = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            assistant_msg["tool_calls"] = message.tool_calls
        sub_messages.append(assistant_msg)

        tool_calls = message.tool_calls or []
        if not tool_calls:
            break

        for tool_call in tool_calls:
            args = parse_openai_arguments(tool_call.function.arguments)
            handler = TOOL_HANDLERS.get(tool_call.function.name)
            if "_parse_error" in args:
                output = f"Error: Invalid tool arguments for {tool_call.function.name}: {args['_raw']}"
            else:
                output = handler(**args) if handler else f"Unknown tool: {tool_call.function.name}"

            sub_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(output)[:50000]
            })

    return message.content or "(no summary)"


run_subagent = run_subagent_openai


# -- 父 Agent 的工具：基础工具 + task 分发器 --
PARENT_TOOLS = CHILD_TOOLS + [
    {"name": "task", "description": "Spawn a subagent with fresh context. It shares the filesystem but not conversation history.",
     "input_schema": {"type": "object", "properties": {"prompt": {"type": "string"}, "description": {"type": "string", "description": "Short description of the task"}}, "required": ["prompt"]}},
]


def agent_loop_openai(messages: list):
    """父 Agent 的循环（OpenAI）"""
    openai_tools = [{
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        }
    } for tool in PARENT_TOOLS]

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

        tool_calls = message.tool_calls or []
        if not tool_calls:
            return

        for tool_call in tool_calls:
            args = parse_openai_arguments(tool_call.function.arguments)

            if "_parse_error" in args:
                output = f"Error: Invalid tool arguments for {tool_call.function.name}: {args['_raw']}"
            elif tool_call.function.name == "task":
                desc = args.get("description", "subtask")
                print(f"> task ({desc}): {args['prompt'][:80]}")
                output = run_subagent(args["prompt"])
            else:
                handler = TOOL_HANDLERS.get(tool_call.function.name)
                output = handler(**args) if handler else f"Unknown tool: {tool_call.function.name}"

            print(f"  {str(output)[:200]}")
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(output)
            })


agent_loop = agent_loop_openai


if __name__ == "__main__":
    history = []
    print("子 Agent 示例 - 父 Agent 可以派发独立任务给子 Agent")
    print("试试：'探索这个项目的结构，告诉我有哪些主要文件'")
    print("观察子 Agent 如何在独立上下文中工作！")
    print()

    while True:
        try:
            query = input("\033[36ms04 >> \033[0m")
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
