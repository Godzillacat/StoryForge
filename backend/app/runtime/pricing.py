"""token 估算与费用计算。

估算用于「生成前预估」与流式返回缺 usage 时的兜底；
真实 usage 由模型返回并覆盖估算值。
"""

from __future__ import annotations

import math

_CJK_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x3040, 0x30FF),
    (0xAC00, 0xD7AF),
)


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in _CJK_RANGES)


def estimate_tokens(text: str) -> int:
    """中日韩字符约 1 token/字，其余约 4 字符/token。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if _is_cjk(ch))
    other = len(text) - cjk
    return max(1, cjk + math.ceil(other / 4))


def compute_cost(prompt_tokens: int, completion_tokens: int, prices: dict | None) -> float:
    """prices 为每百万 token 单价：{"input": x, "output": y}。"""
    if not prices:
        return 0.0
    input_price = float(prices.get("input") or 0.0)
    output_price = float(prices.get("output") or 0.0)
    return (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000


def resolve_prices(
    binding_prices: dict | None, price_row: dict | None
) -> dict | None:
    """单价解析：角色卡绑定里的 prices 优先，其次模型单价表。

    保留绑定优先是为了兼容 P1a 以来的数据与测试；界面上已不再鼓励写它。
    两者都没有时返回 None —— 调用方据此判断这条运行「未定价」，
    而不是把 0 当成「免费」。
    """
    if binding_prices:
        return binding_prices
    if price_row:
        return {
            "input": float(price_row.get("input_price") or 0.0),
            "output": float(price_row.get("output_price") or 0.0),
        }
    return None
