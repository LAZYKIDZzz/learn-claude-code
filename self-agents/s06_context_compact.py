#!/usr/bin/env python3
"""
s06_context_compact.py - 上下文压缩（Context Compaction）

三层压缩管道，让 Agent 可以永久运行：

    每一轮：
    +------------------+
    | 工具调用结果     |
    +------------------+
            |
            v
    [Layer 1: micro_compact]        (静默，每轮执行)
      保留最近 3 个工具结果
      旧结果替换为 "[Previous: used {tool_name}]"
            |
            v
    [检查: tokens > 50000?]
       |               |
       no              yes
       |               |
       v               v
    继续          [Layer 2: auto_compact]
                  保存完整对话到 .transcripts/
                  让 LLM 总结对话
                  用摘要替换所有消息
                        |
                        v
                [Layer 3: compact tool]
                  模型调用 compact -> 立即总结
                  与 auto 相同，手动触发

关键洞察："Agent 可以战略性地遗忘，从而永久工作。"
"""

import json
import json
import os
import subprocess
import time
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

SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks."

# 压缩配置
THRESHOLD = 50000  # Token 阈值：超过此值触发自动压缩
TRANSCRIPT_DIR = WORKDIR / ".transcripts"  # 对话记录保存目录
KEEP_RECENT = 3  # 保留最近 N 个工具结果


def estimate_tokens(messages: list) -> int:
    """
    粗略估算 token 数量

    规则：约 4 个字符 = 1 个 token

    参数:
        messages: 消息列表

    返回:
        估算的 token 数量
    """
    return len(str(messages)) // 4


# -- Layer 1: micro_compact - 用占位符替换旧的工具结果 --
def micro_compact(messages: list) -> list:
    """
    微压缩：保留最近的工具结果，旧的替换为占位符

    这是一个静默的压缩层，每轮都会执行，用户不会察觉。

    策略：
    - 收集所有 tool_result 条目
    - 保留最近 KEEP_RECENT 个
    - 旧的替换为 "[Previous: used {tool_name}]"

    参数:
        messages: 消息列表

    返回:
        压缩后的消息列表
    """
    # 收集所有 tool_result 条目：(msg_index, part_index, tool_result_dict)
    tool_results = []
    for msg_idx, msg in enumerate(messages):
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            for part_idx, part in enumerate(msg["content"]):
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    tool_results.append((msg_idx, part_idx, part))

    # 如果工具结果数量 <= KEEP_RECENT，不需要压缩
    if len(tool_results) <= KEEP_RECENT:
        return messages

    # 通过匹配 tool_use_id 找到每个结果对应的工具名称
    tool_name_map = {}
    for msg in messages:
        if msg["role"] == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        tool_name_map[block.id] = block.name

    # 清除旧结果（保留最后 KEEP_RECENT 个）
    to_clear = tool_results[:-KEEP_RECENT]
    for _, _, result in to_clear:
        if isinstance(result.get("content"), str) and len(result["content"]) > 100:
            tool_id = result.get("tool_use_id", "")
            tool_name = tool_name_map.get(tool_id, "unknown")
            result["content"] = f"[Previous: used {tool_name}]"

    return messages


# -- Layer 2: auto_compact - 保存记录，总结，替换消息 --
def auto_compact(messages: list) -> list:
    """
    自动压缩：保存完整对话，让 LLM 总结，用摘要替换

    这是主要的压缩层，当 token 数量超过阈值时触发。

    流程：
    1. 保存完整对话到 .transcripts/ 目录
    2. 让 LLM 总结对话（保留关键信息）
    3. 用摘要替换所有消息

    参数:
        messages: 消息列表

    返回:
        压缩后的消息列表（只包含摘要）
    """
    # 1. 保存完整对话到磁盘
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    transcript_path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"

    with open(transcript_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")

    print(f"[transcript saved: {transcript_path}]")

    # 2. 让 LLM 总结对话
    conversation_text = json.dumps(messages, default=str)[:80000]  # 限制长度

    if AI_PROVIDER == "anthropic":
        response = client.messages.create(
            model=MODEL,
            messages=[{"role": "user", "content":
                "Summarize this conversation for continuity. Include: "
                "1) What was accomplished, 2) Current state, 3) Key decisions made. "
                "Be concise but preserve critical details.\n\n" + conversation_text}],
            max_tokens=2000,
        )
        summary = response.content[0].text
    else:  # OpenAI
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content":
                "Summarize this conversation for continuity. Include: "
                "1) What was accomplished, 2) Current state, 3) Key decisions made. "
                "Be concise but preserve critical details.\n\n" + conversation_text}],
            max_tokens=2000,
        )
        summary = response.choices[0].message.content

    # 3. 用压缩后的摘要替换所有消息
    return [
        {"role": "user", "content": f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}"},
        {"role": "assistant", "content": "Understood. I have the context from the summary. Continuing."},
    ]


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
    "compact":    lambda **kw: "Manual compression requested.",  # Layer 3: 手动压缩
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
    {"name": "compact", "description": "Trigger manual conversation compression.",
     "input_schema": {"type": "object", "properties": {"focus": {"type": "string", "description": "What to preserve in the summary"}}}},
]


def agent_loop_anthropic(messages: list):
    """Anthropic 的 agent 循环（带三层压缩）"""
    while True:
        # Layer 1: 每次 LLM 调用前执行微压缩
        micro_compact(messages)

        # Layer 2: 如果 token 估算超过阈值，执行自动压缩
        if estimate_tokens(messages) > THRESHOLD:
            print("[auto_compact triggered]")
            messages[:] = auto_compact(messages)

        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return

        results = []
        manual_compact = False  # 标记是否手动触发压缩

        for block in response.content:
            if block.type == "tool_use":
                if block.name == "compact":
                    # Layer 3: 手动压缩
                    manual_compact = True
                    output = "Compressing..."
                else:
                    handler = TOOL_HANDLERS.get(block.name)
                    try:
                        output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                    except Exception as e:
                        output = f"Error: {e}"

                print(f"> {block.name}: {str(output)[:200]}")
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})

        messages.append({"role": "user", "content": results})

        # Layer 3: 如果手动触发了 compact 工具，执行压缩
        if manual_compact:
            print("[manual compact]")
            messages[:] = auto_compact(messages)


def agent_loop_openai(messages: list):
    """OpenAI 的 agent 循环（带三层压缩）"""
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
        # Layer 1: 微压缩
        micro_compact(messages)

        # Layer 2: 自动压缩
        if estimate_tokens(messages) > THRESHOLD:
            print("[auto_compact triggered]")
            messages[:] = auto_compact(messages)

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

        manual_compact = False
        for tool_call in tool_calls:
            args = parse_openai_arguments(tool_call.function.arguments)

            if "_parse_error" in args:
                output = f"Error: Invalid tool arguments for {tool_call.function.name}: {args['_raw']}"
            elif tool_call.function.name == "compact":
                manual_compact = True
                output = "Compressing..."
            else:
                handler = TOOL_HANDLERS.get(tool_call.function.name)
                try:
                    output = handler(**args) if handler else f"Unknown tool: {tool_call.function.name}"
                except Exception as e:
                    output = f"Error: {e}"

            print(f"> {tool_call.function.name}: {str(output)[:200]}")
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(output)
            })

        # Layer 3: 手动压缩
        if manual_compact:
            print("[manual compact]")
            messages[:] = auto_compact(messages)


agent_loop = agent_loop_anthropic if AI_PROVIDER == "anthropic" else agent_loop_openai


if __name__ == "__main__":
    history = []
    print("上下文压缩示例 - Agent 可以永久运行")
    print(f"Token 阈值: {THRESHOLD}")
    print(f"对话记录保存到: {TRANSCRIPT_DIR}")
    print("试试长时间对话，观察自动压缩！")
    print()

    while True:
        try:
            query = input("\033[36ms06 >> \033[0m")
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
