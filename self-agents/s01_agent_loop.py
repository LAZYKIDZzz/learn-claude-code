#!/usr/bin/env python3
"""
s01_agent_loop.py - Agent 循环（核心模式）

AI 编码 Agent 的核心秘密就在这一个模式中：

    while stop_reason == "tool_use":
        response = LLM(messages, tools)  # 调用大模型
        execute tools                     # 执行工具
        append results                    # 追加结果

    +----------+      +-------+      +---------+
    |   用户   | ---> |  LLM  | ---> |  工具   |
    |   提示   |      |       |      |  执行   |
    +----------+      +---+---+      +----+----+
                          ^               |
                          |   工具结果    |
                          +---------------+
                          (循环继续)

这是核心循环：将工具结果反馈给模型，直到模型决定停止。
生产环境的 Agent 会在此基础上添加策略、钩子和生命周期控制。
"""

import json
import os
import subprocess

# 支持 Anthropic 和 OpenAI 两种接口
from dotenv import load_dotenv

load_dotenv(override=True)

# 根据环境变量选择使用哪个 AI 提供商
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")  # 默认使用 anthropic

if AI_PROVIDER == "anthropic":
    from anthropic import Anthropic

    # 如果设置了自定义 base_url，移除 auth token（用于代理场景）
    if os.getenv("ANTHROPIC_BASE_URL"):
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

    client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
    MODEL = os.environ.get("MODEL_ID", "claude-3-5-sonnet-20241022")

elif AI_PROVIDER == "openai":
    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL")  # 支持自定义 base_url
    )
    MODEL = os.getenv("MODEL_ID", "gpt-4")
else:
    raise ValueError(f"不支持的 AI_PROVIDER: {AI_PROVIDER}")

# 系统提示词：告诉 AI 它的角色和工作目录
SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

# 工具定义：描述 AI 可以使用的工具
TOOLS = [{
    "name": "bash",
    "description": "Run a shell command.",  # 运行 shell 命令
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
}]


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

    try:
        # 执行命令，捕获输出，设置超时时间为 120 秒
        r = subprocess.run(
            command,
            shell=True,
            cwd=os.getcwd(),
            capture_output=True,  # 捕获 stdout 和 stderr
            text=True,            # 以文本模式返回
            timeout=120           # 超时时间
        )
        out = (r.stdout + r.stderr).strip()
        # 限制输出长度，防止结果过大
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def agent_loop_anthropic(messages: list):
    """
    Anthropic 的 Agent 循环实现

    核心模式：持续调用 LLM，执行工具，直到模型停止调用工具
    """
    while True:
        # 1. 调用 LLM，传入对话历史和可用工具
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM,
            messages=messages,
            tools=TOOLS,
            max_tokens=8000,
        )

        # 2. 将 AI 的回复添加到对话历史
        messages.append({"role": "assistant", "content": response.content})

        # 3. 如果模型没有调用工具，说明任务完成，退出循环
        if response.stop_reason != "tool_use":
            return

        # 4. 执行每个工具调用，收集结果
        results = []
        for block in response.content:
            if block.type == "tool_use":
                # 打印正在执行的命令（黄色）
                print(f"\033[33m$ {block.input['command']}\033[0m")
                # 执行 bash 命令
                output = run_bash(block.input["command"])
                # 打印输出的前 200 个字符
                print(output[:200])
                # 构造工具结果
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output
                })

        # 5. 将工具结果作为用户消息添加到对话历史
        messages.append({"role": "user", "content": results})


def agent_loop_openai(messages: list):
    """
    OpenAI 的 Agent 循环实现

    OpenAI 的 API 格式与 Anthropic 略有不同，但核心逻辑相同
    """
    # 将工具定义转换为 OpenAI 格式（function calling）
    openai_tools = [{
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            }
        }
    }]

    def parse_openai_arguments(raw: str) -> dict:
        """
        解析 OpenAI 工具参数（arguments 是 JSON 字符串）

        返回解析后的 dict；如果解析失败，返回包含错误信息的占位 dict。
        """
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            return {"_parse_error": str(e), "_raw": raw}

    while True:
        # 1. 调用 OpenAI API
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM}] + messages,
            tools=openai_tools,
            max_tokens=8000,
        )

        # 调试：检查响应类型
        if isinstance(response, str):
            print(f"错误：API 返回了字符串而不是对象: {response[:200]}")
            return

        message = response.choices[0].message

        # 2. 将 AI 的回复添加到对话历史
        assistant_msg = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            assistant_msg["tool_calls"] = message.tool_calls
        messages.append(assistant_msg)

        # 3. 如果没有工具调用，退出循环
        tool_calls = message.tool_calls or []
        if not tool_calls:
            return

        # 4. 执行每个工具调用
        for tool_call in tool_calls:
            if tool_call.function.name == "bash":
                args = parse_openai_arguments(tool_call.function.arguments)
                if "_parse_error" in args or "command" not in args:
                    raw = args.get("_raw", "")
                    output = f"Error: Invalid tool arguments for bash: {raw}"
                    print(output[:200])
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": output
                    })
                    continue
                command = args["command"]

                # 打印正在执行的命令
                print(f"\033[33m$ {command}\033[0m")
                output = run_bash(command)
                print(output[:200])

                # 5. 将工具结果添加到对话历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(output)
                })


# 根据 AI 提供商选择对应的循环函数
agent_loop = agent_loop_anthropic if AI_PROVIDER == "anthropic" else agent_loop_openai


if __name__ == "__main__":
    """
    主程序：实现一个简单的交互式命令行界面
    """
    history = []  # 对话历史

    while True:
        try:
            # 读取用户输入（青色提示符）
            query = input("\033[36ms01 >> \033[0m")
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

        # 打印 AI 的文本回复
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        elif isinstance(response_content, str) and response_content.strip():
            print(response_content)
        print()
