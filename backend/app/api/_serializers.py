"""api 层共用的 ORM→dict 序列化器。

与 schemas.py 分工：schemas.py 只放 Pydantic 出入参模型，这里放跨路由复用的响应整形。
"""

from __future__ import annotations


def _idea_out(idea) -> dict:
    return {
        "id": idea.id,
        "project_id": idea.project_id,
        "raw_text": idea.raw_text,
        "tags": idea.tags_json,
        "parsed_json": idea.parsed_json,
        "status": idea.status,
    }
