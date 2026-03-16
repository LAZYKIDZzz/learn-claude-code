#!/usr/bin/env python3
"""
s05_skill_loading.py - 技能系统（Skills）

两层技能注入，避免系统提示词膨胀：

    Layer 1（轻量）：系统提示词中的技能名称（~100 tokens/技能）
    Layer 2（按需）：工具结果中的完整技能内容

    skills/
      pdf/
        SKILL.md          <-- frontmatter（名称、描述）+ 正文
      code-review/
        SKILL.md

    系统提示词：
    +--------------------------------------+
    | You are a coding agent.              |
    | Skills available:                    |
    |   - pdf: Process PDF files...        |  <-- Layer 1: 仅元数据
    |   - code-review: Review code...      |
    +--------------------------------------+

    当模型调用 load_skill("pdf"):
    +--------------------------------------+
    | tool_result:                         |
    | <skill>                              |
    |   完整的 PDF 处理说明                |  <-- Layer 2: 完整内容
    |   Step 1: ...                        |
    |   Step 2: ...                        |
    | </skill>                             |
    +--------------------------------------+

关键洞察："不要把所有东西都放在系统提示词里。按需加载。"
"""

import json
import os
import re
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
SKILLS_DIR = WORKDIR / "skills"


# -- SkillLoader: 扫描 skills/<name>/SKILL.md，解析 YAML frontmatter --
class SkillLoader:
    """
    技能加载器

    扫描 skills/ 目录下的所有 SKILL.md 文件，解析其中的：
    - YAML frontmatter（元数据：名称、描述、标签）
    - 正文内容（详细的技能说明）

    技能文件格式：
    ---
    name: pdf
    description: Process PDF files
    tags: document, parsing
    ---

    详细的 PDF 处理步骤...
    """

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills = {}  # {技能名: {meta, body, path}}
        self._load_all()

    def _load_all(self):
        """扫描并加载所有技能文件"""
        if not self.skills_dir.exists():
            return

        # 递归查找所有 SKILL.md 文件
        for f in sorted(self.skills_dir.rglob("SKILL.md")):
            text = f.read_text()
            meta, body = self._parse_frontmatter(text)
            # 技能名称：优先使用 frontmatter 中的 name，否则使用目录名
            name = meta.get("name", f.parent.name)
            self.skills[name] = {"meta": meta, "body": body, "path": str(f)}

    def _parse_frontmatter(self, text: str) -> tuple:
        """
        解析 YAML frontmatter

        格式：
        ---
        key1: value1
        key2: value2
        ---
        正文内容...

        返回:
            (meta_dict, body_text)
        """
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text

        meta = {}
        # 简单的 YAML 解析（只支持 key: value 格式）
        for line in match.group(1).strip().splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                meta[key.strip()] = val.strip()

        return meta, match.group(2).strip()

    def get_descriptions(self) -> str:
        """
        Layer 1: 获取简短描述，用于系统提示词

        返回格式：
          - pdf: Process PDF files [document, parsing]
          - code-review: Review code quality
        """
        if not self.skills:
            return "(no skills available)"

        lines = []
        for name, skill in self.skills.items():
            desc = skill["meta"].get("description", "No description")
            tags = skill["meta"].get("tags", "")
            line = f"  - {name}: {desc}"
            if tags:
                line += f" [{tags}]"
            lines.append(line)

        return "\n".join(lines)

    def get_content(self, name: str) -> str:
        """
        Layer 2: 获取完整技能内容，在工具结果中返回

        参数:
            name: 技能名称

        返回:
            包装在 <skill> 标签中的完整技能内容
        """
        skill = self.skills.get(name)
        if not skill:
            return f"Error: Unknown skill '{name}'. Available: {', '.join(self.skills.keys())}"

        return f"<skill name=\"{name}\">\n{skill['body']}\n</skill>"


# 全局技能加载器实例
SKILL_LOADER = SkillLoader(SKILLS_DIR)

# Layer 1: 技能元数据注入到系统提示词
SYSTEM = f"""You are a coding agent at {WORKDIR}.
Use load_skill to access specialized knowledge before tackling unfamiliar topics.

Skills available:
{SKILL_LOADER.get_descriptions()}"""


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
    "load_skill": lambda **kw: SKILL_LOADER.get_content(kw["name"]),  # 新增：加载技能
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
    {"name": "load_skill", "description": "Load specialized knowledge by name.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "Skill name to load"}}, "required": ["name"]}},
]


def agent_loop_openai(messages: list):
    """OpenAI 的 agent 循环"""
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

        tool_calls = message.tool_calls or []
        if not tool_calls:
            return

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


agent_loop = agent_loop_openai


if __name__ == "__main__":
    history = []
    print("技能系统示例 - AI 可以按需加载专业知识")
    print(f"技能目录: {SKILLS_DIR}")
    print("创建示例技能：")
    print("  mkdir -p skills/example")
    print("  echo '---\\nname: example\\ndescription: Example skill\\n---\\nThis is an example.' > skills/example/SKILL.md")
    print()

    while True:
        try:
            query = input("\033[36ms05 >> \033[0m")
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
