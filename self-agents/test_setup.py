#!/usr/bin/env python3
"""
test_setup.py - 环境配置测试脚本

运行这个脚本来验证你的环境是否配置正确。
"""

import sys
import os
from pathlib import Path

def test_python_version():
    """测试 Python 版本"""
    print("🔍 检查 Python 版本...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro} (需要 >= 3.8)")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} (需要 >= 3.8)")
        return False


def test_dependencies():
    """测试依赖包"""
    print("\n🔍 检查依赖包...")

    packages = {
        "openai": "OpenAI SDK",
        "dotenv": "python-dotenv"
    }

    all_ok = True
    for package, name in packages.items():
        try:
            if package == "dotenv":
                __import__("dotenv")
            else:
                __import__(package)
            print(f"   ✅ {name}")
        except ImportError:
            print(f"   ❌ {name} (运行: pip install {package if package != 'dotenv' else 'python-dotenv'})")
            all_ok = False

    return all_ok


def test_env_file():
    """测试 .env 文件"""
    print("\n🔍 检查 .env 文件...")

    env_path = Path(".env")
    if not env_path.exists():
        print("   ⚠️  .env 文件不存在")
        print("   💡 运行: cp .env.example .env")
        print("   💡 然后编辑 .env 文件，填入你的 API 密钥")
        return False

    print("   ✅ .env 文件存在")

    # 加载 .env
    from dotenv import load_dotenv
    load_dotenv(override=True)

    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key and api_key != "your_openai_api_key_here":
        print(f"   ✅ OPENAI_API_KEY 已配置 ({api_key[:10]}...)")
        return True
    else:
        print("   ❌ OPENAI_API_KEY 未配置或使用默认值")
        print("   💡 在 .env 中设置: OPENAI_API_KEY=sk-xxxxx")
        return False


def test_api_connection():
    """测试 API 连接"""
    print("\n🔍 测试 API 连接...")

    from dotenv import load_dotenv
    load_dotenv(override=True)

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
        model = os.getenv("MODEL_ID", "gpt-4")

        print(f"   📡 连接到 OpenAI API (模型: {model})...")

        response = client.chat.completions.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )

        print("   ✅ API 连接成功！")
        print(f"   💬 测试响应: {response.choices[0].message.content}")
        return True

    except Exception as e:
        print(f"   ❌ API 连接失败: {e}")
        print("   💡 检查:")
        print("      - API 密钥是否正确")
        print("      - 网络连接是否正常")
        print("      - 模型名称是否正确")
        return False


def main():
    """主测试流程"""
    print("=" * 60)
    print("🚀 AI Agent 环境配置测试")
    print("=" * 60)

    results = []

    # 1. Python 版本
    results.append(("Python 版本", test_python_version()))

    # 2. 依赖包
    results.append(("依赖包", test_dependencies()))

    # 3. .env 文件
    results.append((".env 配置", test_env_file()))

    # 4. API 连接（只有前面都通过才测试）
    if all(r[1] for r in results):
        results.append(("API 连接", test_api_connection()))
    else:
        print("\n⏭️  跳过 API 连接测试（请先解决上述问题）")

    # 总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)

    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"   {status} - {name}")

    all_passed = all(r[1] for r in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 恭喜！所有测试通过，你可以开始使用了！")
        print("\n下一步:")
        print("   python s01_agent_loop.py")
        print("\n或查看快速开始指南:")
        print("   cat QUICKSTART.md")
    else:
        print("⚠️  部分测试失败，请根据上述提示解决问题。")
        print("\n需要帮助？查看:")
        print("   - QUICKSTART.md (快速开始)")
        print("   - README.md (完整指南)")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
