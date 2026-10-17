import json

from app.world_types import CHARACTER_FIELDS, ENTRY_TYPES, HARDNESS_LEVELS


def test_entry_types_endpoint_is_the_frontends_only_source(client):
    payload = client.get("/api/entry-types").json()

    assert {t["key"]: t["label"] for t in payload["types"]} == ENTRY_TYPES
    assert {h["key"]: h["label"] for h in payload["hardness"]} == HARDNESS_LEVELS
    # 顺序稳定，前端不必再排一次
    assert [t["key"] for t in payload["types"]] == list(ENTRY_TYPES)


def test_entry_types_lists_character_fields(client):
    payload = client.get("/api/entry-types").json()

    assert [f["key"] for f in payload["character_fields"]] == list(CHARACTER_FIELDS)
    assert payload["character_fields"][0] == {
        "key": "appearance",
        "label": "外貌",
        "multiline": True,
    }


def test_entry_crud_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    created = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"type": "势力", "name": "记忆交易局", "aliases": ["交易局"], "tags": ["机构"]},
    ).json()
    assert created["type"] == "faction"  # 中文名被归一化
    assert created["aliases"] == ["交易局"]
    assert created["hardness"] is None

    listed = client.get(f"/api/projects/{project['id']}/entries", params={"type": "faction"}).json()
    assert [e["id"] for e in listed] == [created["id"]]

    updated = client.patch(f"/api/entries/{created['id']}", json={"summary": "管记忆买卖"}).json()
    assert updated["summary"] == "管记忆买卖"
    assert updated["name"] == "记忆交易局"  # 没传的字段不动

    assert client.delete(f"/api/entries/{created['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}/entries").json() == []


def test_duplicate_name_over_http_is_a_readable_400(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    body = {"type": "place", "name": "雾港旧城"}
    client.post(f"/api/projects/{project['id']}/entries", json=body)

    response = client.post(f"/api/projects/{project['id']}/entries", json=body)

    assert response.status_code == 400
    assert "雾港旧城" in response.json()["detail"]


def test_relation_crud_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    a = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "faction", "name": "甲"}
    ).json()
    b = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "place", "name": "乙"}
    ).json()

    relation = client.post(
        f"/api/projects/{project['id']}/relations",
        json={"from_id": a["id"], "to_id": b["id"], "kind": "位于"},
    ).json()
    assert relation["kind"] == "位于"

    assert client.get(f"/api/projects/{project['id']}/relations").json()[0]["id"] == relation["id"]
    assert client.delete(f"/api/relations/{relation['id']}").status_code == 204
    assert client.get(f"/api/projects/{project['id']}/relations").json() == []


def test_deleting_an_entry_removes_it_from_relations_list(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    a = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "faction", "name": "甲"}
    ).json()
    b = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "place", "name": "乙"}
    ).json()
    client.post(
        f"/api/projects/{project['id']}/relations",
        json={"from_id": a["id"], "to_id": b["id"], "kind": "位于"},
    )

    client.delete(f"/api/entries/{a['id']}")

    assert client.get(f"/api/projects/{project['id']}/relations").json() == []


CANDIDATES = (
    '{"entries": ['
    '{"type": "势力", "name": "记忆交易局", "aliases": ["交易局"],'
    ' "summary": "管记忆买卖的机构", "description": "", "hardness": ""},'
    '{"type": "规则体系", "name": "记忆不可复活", "aliases": [],'
    ' "summary": "硬规则", "description": "", "hardness": "硬规则"},'
    '{"type": "地理", "name": "雾港旧城", "aliases": ["旧城"],'
    ' "summary": "故事发生的南方小城", "description": "", "hardness": ""}],'
    ' "open_questions": ["记忆交易合法吗？"]}'
)
# 注意是 **3** 条：契约里 entries 有 minItems: 3，只给 2 条连校验都过不去。


def _seed_slots(project_id: str) -> None:
    """替测试补上世界观构建师要吃的前置条件：已解析的灵感与已采纳的架构。

    它的提示词引用了 parsed_idea 与 story_bible 两个槽位。槽位取不到值时
    build_context 会把它丢掉、render 随即抛 MissingVariableError，整个 run
    变成 template 错误 —— 这是产品行为（上游没做就别跑下游），不是测试
    特例，所以在这里补前置。与 client 夹具里补服务商、补模型绑定同一条路子。
    """
    from app.db.models import Architecture, Idea
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
        session.add(
            Architecture(
                project_id=project_id,
                logline="记忆清洁工在待销毁档案里听见自己的声音",
                theme="不被删除的记忆才证明一个人活过",
            )
        )
        session.commit()


def _patch_runtime(monkeypatch, content: str) -> None:
    """把运行时用的 HTTP 客户端换成固定响应的假实现。

    替换的是 RuntimeService._resolve_client 而不是 HttpxChatClient：
    后者在模块 import 时已被绑定，patch 模块属性不会影响已绑定的名字。
    """
    import httpx

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


def test_suggest_returns_structured_candidates(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_slots(project["id"])
    _patch_runtime(monkeypatch, CANDIDATES)

    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()

    assert body["structured"] is True
    assert body["parse_error"] is None
    assert [e["name"] for e in body["entries"]] == ["记忆交易局", "记忆不可复活", "雾港旧城"]
    assert body["open_questions"] == ["记忆交易合法吗？"]
    assert body["run"]["rendered_prompt"]  # 调试台要能看完整链路


def test_suggest_degrades_without_losing_the_raw_text(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_slots(project["id"])
    _patch_runtime(monkeypatch, "模型没按格式返回")

    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()

    assert body["structured"] is False
    assert body["entries"] == []
    assert body["parse_error"]
    assert body["raw_text"] == "模型没按格式返回"


def test_suggest_on_a_bare_project_tells_the_author_what_to_do_first(client, monkeypatch):
    """没解析过灵感、没采纳过架构时，世界观构建师的两个槽位是空的。

    这时不该给作者一句「模型没按契约返回」—— 模型根本没被调用，
    那是句假话，而且作者照它排查会找到错的方向。要给一句能照做的。
    """
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _patch_runtime(monkeypatch, CANDIDATES)

    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()

    assert body["structured"] is False
    assert body["entries"] == []
    assert "灵感" in body["parse_error"]
    assert "架构" in body["parse_error"]


def test_suggest_writes_no_entries_until_adopted(client, monkeypatch):
    """候选只落在运行记录里（D-04）—— 跑一次不该往表里写任何东西。"""
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_slots(project["id"])
    _patch_runtime(monkeypatch, CANDIDATES)

    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()

    # 先确认这次真的产出了候选 —— 否则「没写库」可能只是因为跑失败了，
    # 这条测试就变成在断言「失败也不写库」，失去它想锁住的东西。
    assert body["structured"] is True
    assert len(body["entries"]) == 3
    assert client.get(f"/api/projects/{project['id']}/entries").json() == []


def test_adopting_a_candidate_records_its_source_run(client, monkeypatch):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_slots(project["id"])
    _patch_runtime(monkeypatch, CANDIDATES)
    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()
    run_id = body["run"]["id"]
    candidate = body["entries"][0]

    created = client.post(
        f"/api/projects/{project['id']}/entries",
        json={
            "type": candidate["type"],
            "name": candidate["name"],
            "aliases": candidate["aliases"],
            "summary": candidate["summary"],
            "source_run_id": run_id,
        },
    ).json()

    assert created["source_run_id"] == run_id
    assert created["type"] == "faction"


def test_candidates_come_back_normalized(client, monkeypatch):
    """模型按契约块里教它的中文值返回类型与硬度，归一化要在边界做一次。

    否则界面拿「规则体系」去匹配英文键的下拉会落空：类型显示成第一个
    选项，规则类的硬度控件也不出现 —— 而硬度正是提示词要求模型为规则
    类填的那一项。
    """
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_slots(project["id"])
    _patch_runtime(monkeypatch, CANDIDATES)

    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()

    assert [e["type"] for e in body["entries"]] == ["faction", "rule", "place"]
    assert [e["hardness"] for e in body["entries"]] == [None, "hard", None]


def test_an_unknown_type_is_left_as_is(client, monkeypatch):
    """归一不了就原样留着：作者会在表单里看到它并改掉，采纳时才报可读错误 ——
    整批候选不该因为一条怪类型而拿不到。"""
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_slots(project["id"])
    _patch_runtime(monkeypatch, CANDIDATES.replace("规则体系", "魔法体系"))

    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()

    assert body["structured"] is True
    assert body["entries"][1]["type"] == "魔法体系"


def _candidates_with(**overrides) -> str:
    """在同一份候选上改几个键，免得把整份 payload 抄第二遍。"""
    payload = json.loads(CANDIDATES)
    payload.update(overrides)
    return json.dumps(payload)


def test_null_open_questions_comes_back_as_an_empty_list(client, monkeypatch):
    """契约校验器现在放过可选字段的 null，接口就必须把它归一成空列表。

    `open_questions` 是可选字段，模型写成显式 null 是「这项为空」的另一种
    写法。前端 `World.tsx` 直接把它塞进 state、随后读 `.length` —— 返回
    `None` 会当场抛 `null.length`。归一在边界做一次（与 _normalized_candidates
    同一条路数：纯逻辑、能被 pytest 覆盖），而不是让前端再抄一份守卫。
    """
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    _seed_slots(project["id"])
    _patch_runtime(monkeypatch, _candidates_with(open_questions=None))

    body = client.post(f"/api/projects/{project['id']}/entries/suggest").json()

    # 先钉住这次真的结构化通过了 —— 否则「返回空列表」可能只是因为整批降级，
    # 这条测试就变成在断言「失败也给空列表」，失去它想锁住的东西。
    assert body["structured"] is True
    assert body["open_questions"] == []
    assert len(body["entries"]) == 3


def test_character_fields_round_trip_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()

    created = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"type": "人物", "name": "陈默", "appearance": "瘦高", "arc_type": "幻灭"},
    ).json()

    assert created["type"] == "character"  # 中文「人物」在边界归一化
    assert created["appearance"] == "瘦高"
    assert created["arc_type"] == "幻灭"
    assert created["personality"] is None  # 没填的就是空

    listed = client.get(f"/api/projects/{project['id']}/entries").json()
    assert listed[0]["appearance"] == "瘦高"


def test_entry_serialization_covers_the_character_field_list(client):
    """序列化输出必须覆盖 CHARACTER_FIELDS 的每一个键。

    与 Task 1 那条「接口下发覆盖字段清单」同一路数：字段清单是唯一真相，
    输出从它派生（`_entry_out` 里的 `**{key: getattr(entry, key) ...}`）。
    将来给清单加第九项、却没有对应的列时，这里当场炸（AttributeError →
    500），而不是安静地少输出一个键 —— 那时作者会发现字段填了却存不下来。
    """
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    created = client.post(
        f"/api/projects/{project['id']}/entries",
        json={"type": "人物", "name": "陈默", "appearance": "瘦高"},
    ).json()

    assert set(CHARACTER_FIELDS) <= set(created)

    # 列表路径单独走一遍：它读的是重新从库里取的对象，不是刚写的那个
    listed = client.get(f"/api/projects/{project['id']}/entries").json()
    assert set(CHARACTER_FIELDS) <= set(listed[0])


def test_relation_strength_and_reverse_over_http(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    a = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "陈默"}
    ).json()
    b = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "林晚"}
    ).json()

    created = client.post(
        f"/api/projects/{project['id']}/relations",
        json={
            "from_id": a["id"],
            "to_id": b["id"],
            "kind": "挚友",
            "strength": 4,
            "create_reverse": True,
        },
    ).json()
    assert created["strength"] == 4

    relations = client.get(f"/api/projects/{project['id']}/relations").json()
    assert len(relations) == 2
    reverse = next(r for r in relations if r["from_id"] == b["id"])

    updated = client.patch(
        f"/api/relations/{reverse['id']}",
        json={"kind": "陌路", "strength": 1, "note": "渐生忌惮"},
    ).json()
    assert updated["kind"] == "陌路"
    assert updated["strength"] == 1
    assert updated["note"] == "渐生忌惮"


def test_relation_strength_out_of_range_is_422(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    a = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "甲"}
    ).json()
    b = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "乙"}
    ).json()

    response = client.post(
        f"/api/projects/{project['id']}/relations",
        json={"from_id": a["id"], "to_id": b["id"], "kind": "挚友", "strength": 6},
    )

    assert response.status_code == 422


def test_relation_update_can_clear_strength(client):
    project = client.post("/api/projects", json={"name": "雾港"}).json()
    a = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "甲"}
    ).json()
    b = client.post(
        f"/api/projects/{project['id']}/entries", json={"type": "人物", "name": "乙"}
    ).json()
    relation = client.post(
        f"/api/projects/{project['id']}/relations",
        json={"from_id": a["id"], "to_id": b["id"], "kind": "挚友", "strength": 3},
    ).json()

    updated = client.patch(
        f"/api/relations/{relation['id']}", json={"strength": None}
    ).json()

    assert updated["strength"] is None


def test_updating_a_missing_relation_is_404(client):
    response = client.patch("/api/relations/nope", json={"kind": "挚友"})
    assert response.status_code == 404
