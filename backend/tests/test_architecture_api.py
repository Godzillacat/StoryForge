"""架构推荐接口（`app/api/architecture.py`）。

核心是一条边界约定：契约校验器放过可选字段的 null，但接口交给前端的形状
必须是**前端能直接用的** —— `story_bible_v0` 得是对象，不是 `None`。
"""

import json

import httpx

from app.runtime.llm import HttpxChatClient

# options 有 minItems: 2，只给一套方案连校验都过不去。
OPTIONS = {
    "options": [
        {"tool": "三幕", "reason": "悬疑的经典骨架", "fit_score": 0.86, "risks": ["中段易松"]},
        {"tool": "双线", "reason": "双主角各推一条线", "fit_score": 0.79, "risks": ["线索易乱"]},
    ],
    "story_bible_v0": None,  # 可选字段的显式 null，见下方用例
}


def _seed_parsed_idea(project_id: str) -> None:
    """补上架构师要吃的前置条件：已解析的灵感。

    它的提示词引用 parsed_idea（另有 project_core 与 tool_library：前者由项目
    行本身提供，后者由 client 夹具的 seed_tools 提供）。取不到值会让 run 变成
    template 错误、structured 直接为 False —— 那是产品行为，不是测试特例。
    与 test_world_api 的 _seed_slots 同一条路子。
    """
    from app.db.models import Idea
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        idea = Idea(project_id=project_id, raw_text="能听见死者遗言的验尸官")
        idea.parsed_json = {
            "genre": "悬疑",
            "premise": "记忆可以被买卖的南方小城",
            "protagonist_desire": "查清那段声音的来处",
            "conflict_source": "个人真相与记忆交易秩序对撞",
            "open_questions": [],
        }
        session.add(idea)
        session.commit()


def _patch_runtime(monkeypatch, content: str) -> None:
    """把运行时用的 HTTP 客户端换成固定响应的假实现。

    替换的是 RuntimeService._resolve_client 而不是 HttpxChatClient：后者在
    模块 import 时已被绑定，patch 模块属性不会影响已绑定的名字。
    """
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


def test_null_story_bible_comes_back_as_an_empty_object(client, monkeypatch):
    """契约校验器现在放过可选字段的 null，接口就必须把它归一成空对象。

    `story_bible_v0` 是可选字段，模型写成显式 null 是「这次没给」的另一种
    写法。前端 `Architecture.tsx` 直接对 `result.story_bible_v0` 取 `.logline`
    —— 返回 `None` 会当场抛错，作者看到一句读不懂的 `null (reading 'logline')`，
    而且故事圣经草稿不会被填充。

    `.get(key, {})` 的默认值**只在缺键时生效**，显式 null 会原样返回 None；
    所以要在这里再兜一次。归一在边界做一次，而不是让前端抄第二份守卫。
    """
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_parsed_idea(project["id"])
    _patch_runtime(monkeypatch, json.dumps(OPTIONS))

    body = client.post(f"/api/projects/{project['id']}/architecture/recommend").json()

    # 先钉住这次真的结构化通过了 —— 否则「返回空对象」可能只是因为整批降级，
    # 这条测试就变成在断言「失败也给空对象」，失去它想锁住的东西。
    assert body["structured"] is True
    assert body["story_bible_v0"] == {}
    # options 是必填，null 仍会被校验器拒 —— 不受本次放宽影响，照常返回。
    assert [o["tool"] for o in body["options"]] == ["三幕", "双线"]


def test_a_present_story_bible_is_passed_through(client, monkeypatch):
    """兜底只该在空值上生效：模型真给了故事圣经，就得原样带回来。"""
    payload = dict(OPTIONS)
    payload["story_bible_v0"] = {"logline": "在待销毁档案里听见自己的声音"}
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_parsed_idea(project["id"])
    _patch_runtime(monkeypatch, json.dumps(payload))

    body = client.post(f"/api/projects/{project['id']}/architecture/recommend").json()

    assert body["structured"] is True
    assert body["story_bible_v0"]["logline"] == "在待销毁档案里听见自己的声音"


# ---- 锁定（P4a）----

def _adopt_body():
    return {
        "logline": "在待销毁档案里听见自己的声音",
        "acts": [{"seq": 1, "name": "第一幕", "purpose": "建置"}],
    }


def test_adopt_is_rejected_when_the_architecture_is_locked(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    first = client.put(f"/api/projects/{project['id']}/architecture", json=_adopt_body())
    assert first.status_code == 200
    arch_id = first.json()["architecture"]["id"]

    locked = client.patch(
        f"/api/locks/architecture/{arch_id}", json={"locked": True}
    )
    assert locked.status_code == 200
    assert locked.json()["locked"] is True

    response = client.put(
        f"/api/projects/{project['id']}/architecture",
        json={**_adopt_body(), "logline": "改过的"},
    )

    assert response.status_code == 409
    assert "已锁定" in response.json()["detail"]

    stored = client.get(f"/api/projects/{project['id']}/architecture").json()
    assert stored["architecture"]["logline"] == "在待销毁档案里听见自己的声音"


def test_adopt_still_works_after_unlocking(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    arch_id = client.put(
        f"/api/projects/{project['id']}/architecture", json=_adopt_body()
    ).json()["architecture"]["id"]
    client.patch(f"/api/locks/architecture/{arch_id}", json={"locked": True})
    client.patch(f"/api/locks/architecture/{arch_id}", json={"locked": False})

    response = client.put(
        f"/api/projects/{project['id']}/architecture",
        json={**_adopt_body(), "logline": "改过的"},
    )

    assert response.status_code == 200
    assert response.json()["architecture"]["logline"] == "改过的"
