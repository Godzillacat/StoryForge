"""提示词渲染。

用 Jinja2 之外的轻量替换：模板里只有 `{{ 变量名 }}` 一种语法，
变量名用英文且必须与槽位键一致。缺变量默认直接报错，不静默留空；
纯文本执笔等「槽位天然可能为空」的预置可显式 `allow_missing=True`，
缺的槽位按空串渲染。
"""

from __future__ import annotations

import re

_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class MissingVariableError(ValueError):
    """模板引用了未提供的变量。渲染失败不静默，让作者看到缺了什么。"""


def render(
    template: str,
    context: dict[str, str],
    *,
    allow_missing: bool = False,
) -> str:
    missing: list[str] = []

    def _substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in context:
            missing.append(name)
            if allow_missing:
                return ""
            return match.group(0)
        return context[name]

    rendered = _VAR_RE.sub(_substitute, template)
    if missing and not allow_missing:
        raise MissingVariableError(f"提示词引用了未提供的变量：{'、'.join(sorted(set(missing)))}")
    return rendered
