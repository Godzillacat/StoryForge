"""正文统计的纯函数。"""

from __future__ import annotations


def count_words(text: str | None) -> int:
    """中文写作惯例：按非空白字符数计。空文本返回 0。"""
    if not text:
        return 0
    return sum(1 for char in text if not char.isspace())
