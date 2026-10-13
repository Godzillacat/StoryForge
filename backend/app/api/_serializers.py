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


def _run_out(run) -> dict:
    """运行记录的完整响应形状。

    三个路由（runs / ideas / architecture）曾各写一份，其中一份被悄悄削成子集，
    前端 RunView 因此对不上——这里只留唯一一份，谁都不许再缩减。
    """
    return {
        "id": run.id,
        "project_id": run.project_id,
        "agent_id": run.agent_id,
        "agent_version_id": run.agent_version_id,
        "provider_id": run.provider_id,
        "model": run.model,
        "params": run.params_json,
        "rendered_prompt": run.rendered_prompt,
        "raw_output": run.raw_output,
        "parsed_json": run.parsed_json,
        "structured": run.structured,
        "parse_error": run.parse_error,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "cost_estimate": run.cost_estimate,
        "duration_ms": run.duration_ms,
        "status": run.status,
        "error": run.error_json,
        "trimmed": run.trimmed_json,
        "created_at": run.created_at.isoformat(),
    }
