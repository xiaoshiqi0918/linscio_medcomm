"""
提示词版本管理工具
职责：
  · 读取 PROMPT_VERSIONS.json
  · 更新版本条目
  · 在更新提示词时自动记录版本变更
  · 提供版本比较和历史查询接口
"""

import json
from datetime import date
from pathlib import Path

VERSIONS_FILE = Path(__file__).parent / "PROMPT_VERSIONS.json"


def load_versions() -> dict:
    """加载版本记录文件"""
    if not VERSIONS_FILE.exists():
        return {"_meta": {"schema_version": "1.0", "last_updated": "", "total_prompt_units": 0}}
    with open(VERSIONS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_versions(data: dict) -> None:
    """保存版本记录文件（格式化 JSON，便于 git diff 阅读）"""
    with open(VERSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_version(prompt_name: str) -> dict | None:
    """
    查询单个提示词的版本信息
    prompt_name: 如 'IntroAgent', 'MEDCOMM_SYSTEM_PROMPT'
    """
    data = load_versions()
    for layer in data.values():
        if isinstance(layer, dict) and prompt_name in layer:
            return layer[prompt_name]
    return None


def bump_version(
    prompt_name: str,
    layer_key: str,
    new_version: str,
    changelog_entry: str,
    file_path: str | None = None,
) -> bool:
    """
    更新单个提示词的版本号和 changelog
    在每次修改提示词后调用，保持版本记录与代码同步。

    Args:
        prompt_name:     提示词名称，如 'IntroAgent'
        layer_key:       所在层级，如 'layer_3_narrative'
        new_version:     新版本号，如 '2.1'
        changelog_entry: 变更说明，如 '补充正/反例示范'（日期和版本号自动添加）
        file_path:       文件路径（可选，若提供则更新 file 字段）

    Returns:
        True 表示成功，False 表示 prompt_name 不存在
    """
    data = load_versions()
    today = date.today().isoformat()

    layer = data.get(layer_key)
    if layer is None or prompt_name not in layer:
        return False

    entry = layer[prompt_name]

    # 更新版本号和日期
    entry["version"] = new_version
    entry["last_updated"] = today
    if file_path:
        entry["file"] = file_path

    # 在 changelog 头部插入新条目
    new_log = f"v{new_version} ({today}): {changelog_entry}"
    entry.setdefault("changelog", [])
    entry["changelog"].insert(0, new_log)

    # 更新 _meta
    if "_meta" in data:
        data["_meta"]["last_updated"] = today

    save_versions(data)
    return True


def register_new_prompt(
    prompt_name: str,
    layer_key: str,
    file_path: str,
    initial_changelog: str = "初始版本",
) -> bool:
    """
    注册新的提示词（首次添加时调用）
    自动创建版本条目，版本号从 1.0 开始
    """
    data = load_versions()
    today = date.today().isoformat()

    if layer_key not in data:
        data[layer_key] = {}

    if prompt_name in data[layer_key]:
        return False  # 已存在，使用 bump_version 更新

    data[layer_key][prompt_name] = {
        "version": "1.0",
        "file": file_path,
        "last_updated": today,
        "changelog": [f"v1.0 ({today}): {initial_changelog}"],
    }

    if "_meta" in data:
        data["_meta"]["last_updated"] = today
        data["_meta"]["total_prompt_units"] = sum(
            len(v) for k, v in data.items()
            if k != "_meta" and isinstance(v, dict)
        )
    save_versions(data)
    return True


def get_recently_updated(days: int = 7) -> list[dict]:
    """
    查询最近 N 天内更新过的提示词
    用于 code review 时快速定位变更范围
    """
    from datetime import timedelta

    cutoff = (date.today() - timedelta(days=days)).isoformat()

    data = load_versions()
    result = []
    for layer_key, layer in data.items():
        if layer_key == "_meta" or not isinstance(layer, dict):
            continue
        for name, info in layer.items():
            if info.get("last_updated", "") >= cutoff:
                result.append({
                    "name": name,
                    "layer": layer_key,
                    "version": info["version"],
                    "last_updated": info["last_updated"],
                    "latest_change": info["changelog"][0] if info.get("changelog") else "",
                })
    return sorted(result, key=lambda x: x["last_updated"], reverse=True)


def check_unregistered_agents(agent_class_names: list[str]) -> list[str]:
    """
    检查代码中存在但 PROMPT_VERSIONS.json 中未注册的 Agent
    用于在 CI 中检测漏登记的提示词
    """
    data = load_versions()
    registered = set()
    for layer_key, layer in data.items():
        if layer_key == "_meta" or not isinstance(layer, dict):
            continue
        registered.update(layer.keys())
    return [name for name in agent_class_names if name not in registered]
