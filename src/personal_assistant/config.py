"""模型配置加载。

配置来源优先级（高 → 低）：
1. 环境变量 ``DEEPSEEK_API_KEY``（覆盖文件中的 ``api_key``，便于 CI / 容器部署）
2. ``config/model.json``（项目本地配置，含真实 key，已被 .gitignore 忽略）
3. ``config/model.json.example`` 的默认值（仅作回退，不应含真实 key）

换模型/换供应商时，只需修改 ``model.json`` 里的 ``base_url`` 与 ``model`` 字段，
无需改动代码——只要供应商提供 OpenAI 兼容接口即可。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# 项目根目录（src/personal_assistant/config.py → 上溯两级到项目根）
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = _PROJECT_ROOT / "config"
_DEFAULT_CONFIG_PATH = _CONFIG_DIR / "model.json"
_EXAMPLE_CONFIG_PATH = _CONFIG_DIR / "model.json.example"


@dataclass
class ModelConfig:
    """模型客户端配置。"""

    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    model: str = "deepseek-v4-flash"
    system_prompt: str = "你是一个乐于助人的个人助理，回答简洁、准确。"
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = True
    # 透传给 SDK 的其它任意字段（如 top_p、stop 等），保持向前兼容。
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 环境变量优先：允许不把真实 key 写进文件。
        env_key = os.environ.get("DEEPSEEK_API_KEY")
        if env_key:
            self.api_key = env_key
        if not self.api_key or self.api_key.startswith("sk-your-"):
            raise ConfigError(
                "未找到有效的 API key。请在 config/model.json 填入 api_key，"
                "或设置环境变量 DEEPSEEK_API_KEY。"
            )


class ConfigError(RuntimeError):
    """配置加载或校验失败。"""


def load_config(path: str | Path | None = None) -> ModelConfig:
    """加载模型配置。

    Args:
        path: 指定配置文件路径；默认依次查找 ``config/model.json`` →
            ``config/model.json.example``。
    """
    config_path = Path(path) if path else _resolve_config_path()
    raw = _read_json(config_path)
    # 分离已知字段与额外字段。
    known = {
        "base_url",
        "api_key",
        "model",
        "system_prompt",
        "temperature",
        "max_tokens",
        "stream",
    }
    fields = {k: v for k, v in raw.items() if k in known}
    extra = {k: v for k, v in raw.items() if k not in known and not k.startswith("_")}
    return ModelConfig(**fields, extra=extra)


def _resolve_config_path() -> Path:
    """返回首个存在的配置文件路径。"""
    if _DEFAULT_CONFIG_PATH.exists():
        return _DEFAULT_CONFIG_PATH
    if _EXAMPLE_CONFIG_PATH.exists():
        return _EXAMPLE_CONFIG_PATH
    raise ConfigError(
        f"找不到配置文件：请在 {_CONFIG_DIR} 下创建 model.json （可参照 model.json.example）。"
    )


def _read_json(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"无法读取配置文件 {path}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"配置文件 {path} 不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"配置文件 {path} 顶层应为 JSON 对象。")
    return data
