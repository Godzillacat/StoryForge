"""输出契约校验（上位文档 §5.5）。

只实现 JSON Schema 的实用子集，不引入 jsonschema 依赖。
解析失败时降级为纯文本并标记「未结构化」，不阻塞作者。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
}


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]
    data: Any | None


def _try_parse(candidate: str) -> Any | None:
    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return None


def extract_json(text: str) -> Any | None:
    """从可能带 Markdown 围栏或前后废话的返回里取出 JSON 对象。

    围栏取最后一个可解析的块：模型常在正式答案前先复述一个模板示例，
    取第一个会把示例当成结果，静默返回「格式合法但内容错」的数据。
    宁可解析失败降级为纯文本，也不接受看似合法的错数据。
    """
    if text is None:
        return None
    stripped = text.strip()
    parsed = _try_parse(stripped)
    if parsed is not None:
        return parsed

    for match in reversed(list(_FENCE_RE.finditer(text))):
        parsed = _try_parse(match.group(1).strip())
        if parsed is not None:
            return parsed

    # 没有围栏：取第一个 { 到最后一个 } 之间的片段
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return _try_parse(text[start : end + 1])
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        return _try_parse(text[start : end + 1])
    return None


def _check_type(value: Any, expected: str) -> bool:
    types = _TYPE_MAP.get(expected)
    if types is None:
        return True  # 未知类型不做校验，避免误报
    if expected in ("number", "integer") and isinstance(value, bool):
        return False  # bool 是 int 的子类，但语义上不是数字
    return isinstance(value, types)


def _validate_node(value: Any, schema: dict, path: str, errors: list[str]) -> None:
    expected = schema.get("type")
    if expected and not _check_type(value, expected):
        errors.append(f"{path} 类型应为 {expected}，实际为 {type(value).__name__}")
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} 的取值 {value!r} 不在允许范围 {schema['enum']!r} 内")

    if expected == "object" or isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path} 缺少必填字段 {key}")
        for key, sub_schema in properties.items():
            if key not in value:
                continue
            # 可选字段的显式 null 视同「没提供」：模型把「这项为空」写成 null
            # 是常见形态，而契约里没有 nullable 的表达方式。**必填不在此列** ——
            # 那里 null 是真的缺东西，仍要按类型报错。
            if value[key] is None and key not in required:
                continue
            _validate_node(value[key], sub_schema, f"{path}.{key}", errors)

    if expected == "array" or isinstance(value, list):
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                _validate_node(item, item_schema, f"{path}[{index}]", errors)
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path} 至少需要 {schema['minItems']} 项，实际 {len(value)} 项")


def validate_json(data: Any, schema: dict) -> tuple[bool, list[str]]:
    """校验已解析的数据，返回 (是否通过, 错误清单)。

    关键语义：契约里**可选**字段的显式 `null` 视同缺键、判通过；**必填**字段的
    `null` 不算省略，仍按类型报错（契约没有 nullable 的表达方式，见 `_validate_node`）。
    """
    errors: list[str] = []
    _validate_node(data, schema, "$", errors)
    return (not errors), errors


def apply_contract(raw_text: str, schema: dict | None) -> tuple[Any | None, bool, str | None]:
    """运行时的对外入口：解析模型返回并校验，返回 (解析结果, 是否结构化, 失败原因)。

    校验语义与 `validate_json` 一致 —— 可选字段的显式 `null` 通过，必填字段的
    `null` 仍判失败。
    """
    if not schema:
        return None, False, "该智能体未定义输出结构"
    data = extract_json(raw_text)
    if data is None:
        return None, False, "返回内容不是合法 JSON"
    ok, errors = validate_json(data, schema)
    if not ok:
        return None, False, "；".join(errors)
    return data, True, None
