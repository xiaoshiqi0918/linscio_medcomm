"""
在 CI 中运行，确保：
1. 所有 Agent 类都在 PROMPT_VERSIONS.json 中注册
2. PROMPT_VERSIONS.json 是合法 JSON
3. 所有 version 字段格式合法（x.y）
"""

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSIONS_FILE = ROOT / "backend" / "app" / "agents" / "prompts" / "PROMPT_VERSIONS.json"
AGENTS_DIR = ROOT / "backend" / "app" / "agents"


def check_json_valid():
    """检查 PROMPT_VERSIONS.json 格式合法性"""
    try:
        with open(VERSIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        print("✓ PROMPT_VERSIONS.json 格式合法")
        return data
    except FileNotFoundError:
        print(f"✗ 文件不存在：{VERSIONS_FILE}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ PROMPT_VERSIONS.json 解析失败：{e}")
        sys.exit(1)


def check_version_format(data: dict):
    """检查所有 version 字段格式（x.y）"""
    errors = []
    for layer_key, layer in data.items():
        if layer_key == "_meta" or not isinstance(layer, dict):
            continue
        for name, info in layer.items():
            ver = info.get("version", "")
            if not re.match(r"^\d+\.\d+$", str(ver)):
                errors.append(f"  {name}: 版本号格式不合法 '{ver}'（应为 x.y）")
    if errors:
        print("✗ 版本号格式错误：")
        for e in errors:
            print(e)
        sys.exit(1)
    print("✓ 所有版本号格式合法")


def check_all_agents_registered(data: dict):
    """扫描代码中所有 BaseAgent 子类，检查是否都已注册"""
    registered = set()
    for layer_key, layer in data.items():
        if layer_key == "_meta" or not isinstance(layer, dict):
            continue
        registered.update(layer.keys())

    def _base_name(b):
        if isinstance(b, ast.Name):
            return getattr(b, "id", "") or ""
        if isinstance(b, ast.Attribute):
            return getattr(b, "attr", "") or ""
        return ""

    agent_files = list(AGENTS_DIR.rglob("*.py"))
    unregistered = []
    for f in agent_files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        base_str = _base_name(base)
                        if "BaseAgent" in base_str and node.name != "BaseAgent":
                            if node.name not in registered:
                                rel = f.relative_to(ROOT)
                                unregistered.append(f"  {node.name} (in {rel})")
        except Exception:
            pass

    if unregistered:
        print("✗ 以下 Agent 未在 PROMPT_VERSIONS.json 中注册：")
        for u in unregistered:
            print(u)
        sys.exit(1)
    print(f"✓ 所有 Agent 均已注册（共 {len(registered)} 个提示词单元）")


if __name__ == "__main__":
    data = check_json_valid()
    check_version_format(data)
    check_all_agents_registered(data)
    print("\n✓ 提示词版本检查全部通过")
