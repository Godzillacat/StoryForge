"""修订建议的生成与应用接口（Task 4）。

沿用 `test_world_api.py` 的写法：真实 `TestClient` ＋ 把运行时解析出的 HTTP
客户端换成 `HttpxChatClient(transport=httpx.MockTransport(...))`。这里测的是
**HTTP 边界**（状态码、请求校验、返回形状），service 的内部逻辑由
`test_revision_service.py` 覆盖 —— 所以数据一律从接口或 `SessionLocal` 造，
不复用那边的 session 夹具（它们会把库整表重建，和 TestClient 用的库打架）。
"""

import json

import httpx
from sqlalchemy import select

from app.db.models import Architecture, ChangeLog, GenerationRun, Scene
from app.db.session import SessionLocal

# 候选清单里的场景标签由 impact_service.scene_label 生成，模型必须原样照抄。
_SCENE_LABEL = "第1卷 第1章 场景1"


def _content(suggestions) -> str:
    """按输出契约包一份模型响应（ensure_ascii=False 才是真正的中文）。"""
    return json.dumps({"suggestions": suggestions}, ensure_ascii=False)


_ONE_SUGGESTION = _content(
    [
        {
            "target_label": _SCENE_LABEL,
            "field": "目标",
            "after": "把妹妹的赎金交给掌柜",
            "reason": "动机已改为替妹妹赎罪，这一场还写着找船主",
        }
    ]
)


def _patch_runtime(monkeypatch, content: str) -> None:
    """把运行时的 HTTP 客户端换成固定响应的假实现（沿用 test_world_api）。

    改的是 `RuntimeService._resolve_client` 而不是 `HttpxChatClient`：后者在
    模块 import 时已被绑定，patch 模块属性影响不到那个名字。
    """
    from app.runtime.llm import HttpxChatClient
    from app.services.runtime_service import RuntimeService

    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 15},
            },
        )

    fake = HttpxChatClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(RuntimeService, "_resolve_client", lambda self, timeout: fake)


def _patch_failing_runtime(monkeypatch, message: str = "服务端炸了") -> None:
    """模型调用失败：服务层要把它折成 `llm_status="error"`，而不是 500。"""
    from app.runtime.llm import HttpxChatClient
    from app.services.runtime_service import RuntimeService

    def handler(request):
        return httpx.Response(500, json={"error": {"message": message}})

    fake = HttpxChatClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(RuntimeService, "_resolve_client", lambda self, timeout: fake)


def _seed_story_bible(project_id: str) -> str:
    """故事圣经是影响面分析的入口，也是提示词引用的槽位。"""
    with SessionLocal() as session:
        arch = Architecture(
            project_id=project_id,
            logline="替妹妹赎罪的兄长在雾港寻找失踪的船主",
            theme="不被删除的记忆才证明一个人活过",
        )
        session.add(arch)
        session.commit()
        return arch.id


def _project_with_scene(client, name: str = "雾港") -> dict:
    """一个带故事圣经、一卷一章一场戏的项目。"""
    project = client.post("/api/projects", json={"name": name}).json()
    volume = client.post(
        f"/api/projects/{project['id']}/volumes", json={"name": "第一卷"}
    ).json()
    chapter = client.post(
        f"/api/volumes/{volume['id']}/chapters",
        json={"title": "失踪的船主", "summary": "兄长在码头打听船主的下落"},
    ).json()
    scene = client.post(
        f"/api/chapters/{chapter['id']}/scenes",
        json={
            "goal": "找到船主的下落",
            "conflict": "码头工人不肯开口",
            "turn": "有人递来一张旧船票",
        },
    ).json()
    return {
        "project": project,
        "arch_id": _seed_story_bible(project["id"]),
        "chapter": chapter,
        "scene": scene,
    }


def _generate(client, project_id: str, arch_id: str) -> dict:
    """跑一次生成，返回服务给出的那份 dict（失败时返回 error 形状）。"""
    response = client.post(
        f"/api/projects/{project_id}/impact/revisions",
        json={"target_type": "architecture", "target_id": arch_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_generate_revisions_returns_structured_suggestions(client, monkeypatch):
    data = _project_with_scene(client)
    _patch_runtime(monkeypatch, _ONE_SUGGESTION)

    body = _generate(client, data["project"]["id"], data["arch_id"])

    assert body["llm_status"] == "ok"
    assert body["suggestions"]  # 非空
    assert isinstance(body["dropped"], int)
    assert body["run_id"]

    first = body["suggestions"][0]
    assert first["target_label"] == _SCENE_LABEL
    assert first["target_type"] == "scene"
    assert first["target_id"] == data["scene"]["id"]
    assert first["field"] == "goal"
    # before 一律由服务端现取，模型给不了也改不了。
    assert first["before"] == "找到船主的下落"
    assert first["after"] == "把妹妹的赎金交给掌柜"


def test_generate_revisions_reports_a_model_failure_as_a_result(client, monkeypatch):
    """模型失败是「结果」不是 HTTP 错误：200 + llm_status="error"，不吞也不 500。

    这条同时钉住上面那次目标校验的分寸：它只负责把「目标不存在」变成 404，
    不能顺手把模型失败也变成 4xx/5xx —— 面板要靠这个形状显示中文原因。
    """
    data = _project_with_scene(client)
    _patch_failing_runtime(monkeypatch)

    body = _generate(client, data["project"]["id"], data["arch_id"])

    assert body["llm_status"] == "error"
    assert body["suggestions"] == []
    assert "服务端炸了" in body["warning"]
    assert body["run_id"]  # 失败也留运行记录，调试台查得到


def test_generate_revisions_on_a_missing_target_is_404(client):
    """目标不存在是客户端错误，不能被折成 200 的 llm_status="error"。

    服务层的 `suggest()` 会把所有异常都折成可读结果（这是对的，模型失败
    不该变成 500），代价是 HTTP 层分不出「目标不存在」与「模型失败」。
    所以路由在调服务之前先跑一次只读的影响面分析做目标校验。
    """
    data = _project_with_scene(client)

    response = client.post(
        f"/api/projects/{data['project']['id']}/impact/revisions",
        json={"target_type": "scene", "target_id": "no-such-scene"},
    )

    assert response.status_code == 404
    assert "场景不存在" in response.json()["detail"]


def test_apply_revisions_writes_the_accepted_field(client, monkeypatch):
    data = _project_with_scene(client)
    _patch_runtime(monkeypatch, _ONE_SUGGESTION)
    generated = _generate(client, data["project"]["id"], data["arch_id"])

    response = client.post(
        f"/api/projects/{data['project']['id']}/impact/revisions/apply",
        json={"run_id": generated["run_id"], "accepted": [0]},
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["field"] for item in body["applied"]] == ["goal"]
    assert body["skipped"] == []

    # 真的落库了，而且改动历史记了一条「AI 来源」。
    with SessionLocal() as session:
        assert (
            session.get(Scene, data["scene"]["id"]).goal == "把妹妹的赎金交给掌柜"
        )
        changes = list(
            session.scalars(
                select(ChangeLog).where(ChangeLog.target_id == data["scene"]["id"])
            )
        )
    assert len(changes) == 1
    assert changes[0].source == "ai"
    assert changes[0].summary == "修订建议 · 目标"


def test_apply_revisions_rejects_a_run_from_another_project(client, monkeypatch):
    mine = _project_with_scene(client, "雾港")
    other = _project_with_scene(client, "另一座城")
    _patch_runtime(monkeypatch, _ONE_SUGGESTION)
    generated = _generate(client, mine["project"]["id"], mine["arch_id"])

    response = client.post(
        f"/api/projects/{other['project']['id']}/impact/revisions/apply",
        json={"run_id": generated["run_id"], "accepted": [0]},
    )

    assert response.status_code == 404
    assert "运行记录不存在" in response.json()["detail"]
    # 别的项目的场景一个字都不能动。
    with SessionLocal() as session:
        assert session.get(Scene, other["scene"]["id"]).goal == "找到船主的下落"


def test_apply_revisions_on_an_unknown_run_is_404(client):
    data = _project_with_scene(client)

    response = client.post(
        f"/api/projects/{data['project']['id']}/impact/revisions/apply",
        json={"run_id": "no-such-run", "accepted": [0]},
    )

    assert response.status_code == 404
    assert "运行记录不存在" in response.json()["detail"]


def test_apply_revisions_on_a_run_without_suggestions_is_400(client):
    """运行记录在、但不是一次修订建议运行：400（客户端用了错的 run_id）。"""
    data = _project_with_scene(client)
    with SessionLocal() as session:
        run = GenerationRun(project_id=data["project"]["id"], parsed_json={"open_questions": []})
        session.add(run)
        session.commit()
        run_id = run.id

    response = client.post(
        f"/api/projects/{data['project']['id']}/impact/revisions/apply",
        json={"run_id": run_id, "accepted": [0]},
    )

    assert response.status_code == 400
    assert "没有可应用" in response.json()["detail"]


def test_generate_revisions_with_an_unknown_target_type_is_400(client):
    data = _project_with_scene(client)

    response = client.post(
        f"/api/projects/{data['project']['id']}/impact/revisions",
        json={"target_type": "chapterr", "target_id": "x"},
    )

    assert response.status_code == 400


def test_apply_revisions_requires_a_list_of_indices(client):
    """`accepted` 不是数组时由 FastAPI/Pydantic 挡下，不到路由里。"""
    response = client.post(
        "/api/projects/any-project/impact/revisions/apply",
        json={"run_id": "run-1", "accepted": "不是数组"},
    )

    assert response.status_code == 422


def test_apply_revisions_requires_a_run_id(client):
    response = client.post(
        "/api/projects/any-project/impact/revisions/apply",
        json={"accepted": [0]},
    )

    assert response.status_code == 422
