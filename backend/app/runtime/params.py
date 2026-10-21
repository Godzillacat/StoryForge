"""参数档与采样参数合并。

三档是产品定义的一部分（严谨 / 平衡 / 发散），不是作者数据，所以放在代码里
而不是数据库里 —— 改它要发版，正好留下版本记录。

只写 temperature 与 top_p：不同服务商对 presence_penalty 之类键的接受度不一，
多写一个键就多一分 400 的风险。max_tokens 是容量属性，仍归全局 default_params。
"""

from __future__ import annotations

PARAM_PROFILES: dict[str, dict[str, float]] = {
    "strict": {"temperature": 0.2, "top_p": 0.8},
    "balanced": {"temperature": 0.7, "top_p": 0.9},
    "creative": {"temperature": 1.0, "top_p": 1.0},
}

PARAM_PROFILE_LABELS: dict[str, str] = {
    "strict": "严谨",
    "balanced": "平衡",
    "creative": "发散",
}

_DEFAULT_PROFILE = "balanced"


def resolve_params(
    *,
    profile: str | None,
    default_params: dict | None,
    override: dict | None = None,
) -> tuple[dict, list[str]]:
    """合并顺序：全局默认 ← 参数档 ← 版本级覆盖。

    未知档名回落 balanced 并给一条 warning：settings.json 与老版本库都可能
    带着作者手写过的字符串，报错会让人无从下手。
    """
    warnings: list[str] = []
    name = profile or _DEFAULT_PROFILE
    if name not in PARAM_PROFILES:
        warnings.append(f"未知的参数档「{name}」，已按「平衡」处理")
        name = _DEFAULT_PROFILE

    merged: dict = {
        **(default_params or {}),
        **PARAM_PROFILES[name],
        **(override or {}),
    }
    return merged, warnings
