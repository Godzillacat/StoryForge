import json

import httpx
import pytest

from app.runtime.execute import ExecuteInput, execute_run
from app.runtime.llm import HttpxChatClient

SCHEMA = {
    "type": "object",
    "required": ["genre"],
    "properties": {"genre": {"type": "string"}},
}


class FakeSource:
    def __init__(self, **fields):
        self._fields = fields

    def project_core(self):
        return self._fields.get("project_core")

    def parsed_idea(self):
        return self._fields.get("parsed_idea")

    def raw_idea(self):
        return self._fields.get("raw_idea")

    def story_bible(self):
        return self._fields.get("story_bible")

    def architecture(self):
        return self._fields.get("architecture")

    def tool_library(self):
        return self._fields.get("tool_library")

    def summarize(self, slot_key, text):
        return text[:3]


def _input(**overrides) -> ExecuteInput:
    base = dict(
        project_id="p1",
        agent_id="a1",
        version_id="v1",
        provider_id="pr1",
        model="m1",
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        params={"temperature": 0.5},
        system_prompt="解析这段灵感：{{ raw_idea }}",
        context_slots=["raw_idea"],
        output_schema=SCHEMA,
        token_budget=8000,
        prices={"input": 1.0, "output": 2.0},
    )
    base.update(overrides)
    return ExecuteInput(**base)


def _client(handler):
    return HttpxChatClient(transport=httpx.MockTransport(handler))


def _ok_handler(content: str, prompt_tokens: int = 100, completion_tokens: int = 50):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
            },
        )

    return handler


async def test_successful_run_is_fully_recorded():
    source = FakeSource(raw_idea="能听见死者遗言的验尸官")
    client = _client(_ok_handler('```json\n{"genre": "悬疑"}\n```'))
    result = await execute_run(_input(), source, client)

    assert result.status == "ok"
    assert result.raw_output == '```json\n{"genre": "悬疑"}\n```'
    assert result.parsed == {"genre": "悬疑"}
    assert result.structured is True and result.parse_error is None
    assert result.prompt_tokens == 100 and result.completion_tokens == 50
    assert result.cost_estimate == pytest.approx(0.0002)
    assert result.duration_ms >= 0
    assert result.error is None


async def test_rendered_prompt_reflects_context_and_template():
    source = FakeSource(raw_idea="能听见死者遗言的验尸官")
    result = await execute_run(_input(), source, _client(_ok_handler('{"genre":"悬疑"}')))
    assert result.rendered_prompt.startswith("解析这段灵感：能听见死者遗言的验尸官")


async def test_unstructured_output_degrades_without_error_status():
    source = FakeSource(raw_idea="灵感")
    result = await execute_run(_input(), source, _client(_ok_handler("模型没按格式返回")))
    assert result.status == "ok"
    assert result.structured is False
    assert result.parsed is None
    assert result.parse_error is not None
    assert result.raw_output == "模型没按格式返回"


async def test_schema_violation_degrades_with_reason():
    source = FakeSource(raw_idea="灵感")
    result = await execute_run(_input(), source, _client(_ok_handler('{"genre": 5}')))
    assert result.structured is False
    assert "genre" in (result.parse_error or "")


async def test_provider_error_marks_status_error_and_keeps_reason():
    def handler(request):
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    result = await execute_run(_input(), FakeSource(raw_idea="灵感"), _client(handler))
    assert result.status == "error"
    assert result.error is not None
    assert result.error["kind"] == "rate_limit"
    assert result.raw_output == ""


async def test_trimmed_records_survive_into_result():
    source = FakeSource(raw_idea="灵感" * 500)
    result = await execute_run(
        _input(context_slots=["raw_idea"], token_budget=10), source, _client(_ok_handler("{}"))
    )
    assert result.trimmed  # 非空，界面据此显示「这次砍掉了什么」


async def test_missing_template_variable_is_reported_as_error():
    source = FakeSource(raw_idea=None)  # raw_idea 槽位取不到值
    result = await execute_run(_input(), source, _client(_ok_handler("{}")))
    assert result.status == "error"
    assert "raw_idea" in (result.error or {}).get("message", "")


async def test_contract_block_is_appended_to_the_sent_prompt():
    """契约说明块必须真的发出去，且落库的 rendered_prompt 就是发出那份（D-03）。"""
    sent: dict = {}

    def handler(request):
        sent["body"] = json.loads(request.read().decode())
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    schema = {
        "type": "object",
        "required": ["genre"],
        "properties": {"genre": {"type": "string", "title": "题材"}},
    }
    source = FakeSource(raw_idea="灵感")
    result = await execute_run(_input(output_schema=schema), source, _client(handler))

    assert result.rendered_prompt.startswith("解析这段灵感：灵感")
    assert "- genre（题材）：字符串，必填" in result.rendered_prompt
    # 落库的必须与发出去的一字不差 —— 用解析后的 JSON 比，不能拿原始 body 做子串匹配
    # （body 里的换行是转义过的 \n，跟真字符串对不上）。
    assert sent["body"]["messages"][0]["content"] == result.rendered_prompt


async def test_no_contract_block_when_schema_is_absent():
    source = FakeSource(raw_idea="灵感")
    result = await execute_run(_input(output_schema=None), source, _client(_ok_handler("{}")))

    assert result.rendered_prompt == "解析这段灵感：灵感"
    assert "【输出契约】" not in result.rendered_prompt
