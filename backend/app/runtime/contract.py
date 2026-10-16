"""由输出契约生成给模型看的字段说明。

契约为字段名与中文名的唯一真相：中文名写在属性的 `title` 上（JSON Schema
标准关键字，校验器不读它）。渲染层据此自动生成说明块追加到提示词之后，
于是提示词里不必再手抄一份字段清单 —— 两份独立维护的清单正是键名不一致的根源。
"""

from __future__ import annotations

_TYPE_LABELS = {
    "object": "对象",
    "array": "数组",
    "string": "字符串",
    "number": "数字",
    "integer": "整数",
    "boolean": "布尔值",
}

_HEADER = "【输出契约】返回一个 JSON 对象，键名一律用英文。字段如下："


def describe_contract(schema: dict | None) -> str:
    """空 schema 返回空串：不定义契约的智能体不该被塞一段空说明。"""
    if not schema:
        return ""
    lines: list[str] = [_HEADER]
    _describe_object(schema, lines, depth=1)
    return "\n".join(lines)


def _describe_object(node: dict, lines: list[str], depth: int) -> None:
    required = set(node.get("required") or [])
    for key, sub in (node.get("properties") or {}).items():
        _describe_field(key, sub, key in required, lines, depth)


def _describe_field(
    key: str, node: dict, required: bool, lines: list[str], depth: int
) -> None:
    pad = "  " * depth
    title = node.get("title")
    name = f"{key}（{title}）" if title else key

    parts = [_type_label(node)]
    if node.get("type") == "array":
        item = node.get("items") or {}
        if node.get("minItems"):
            parts.append(f"至少 {node['minItems']} 项")
        if item.get("properties"):
            parts.append("每项是一个对象")
        else:
            parts.append(f"元素是{_type_label(item)}")
    if node.get("enum"):
        parts.append("取值：" + "、".join(str(v) for v in node["enum"]))
    if required:
        parts.append("必填")

    lines.append(f"{pad}- {name}：{'，'.join(parts)}")
    _describe_children(node, lines, depth)


def _describe_children(node: dict, lines: list[str], depth: int) -> None:
    if node.get("type") == "object" and node.get("properties"):
        _describe_object(node, lines, depth + 1)
        return
    if node.get("type") == "array":
        item = node.get("items") or {}
        if item.get("type") == "object" and item.get("properties"):
            _describe_object(item, lines, depth + 1)


def _type_label(node: dict) -> str:
    return _TYPE_LABELS.get(node.get("type") or "", "值")
