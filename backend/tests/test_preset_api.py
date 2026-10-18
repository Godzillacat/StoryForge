def _seeded_agent(client, task_type: str) -> dict:
    agents = client.get("/api/agents").json()
    return next(agent for agent in agents if agent["task_type"] == task_type)


def test_seeded_agents_report_their_preset_status(client):
    agent = _seeded_agent(client, "idea_parse")

    assert agent["preset"]["key"] == "idea_parser"
    assert agent["preset"]["up_to_date"] is True
    assert agent["preset"]["can_restore"] is False


def test_applying_a_preset_creates_a_new_version_and_keeps_model_binding(client):
    agent = _seeded_agent(client, "idea_parse")
    before = agent["current_version"]

    edited = client.post(
        f"/api/agents/{agent['id']}/versions",
        json={"system_prompt": "作者改过的提示词", "note": "手动编辑"},
    ).json()

    assert edited["version_no"] == before["version_no"] + 1
    listed = _seeded_agent(client, "idea_parse")
    assert listed["preset"]["can_restore"] is True
    assert listed["preset"]["update_available"] is False

    applied = client.post(f"/api/agents/{agent['id']}/apply-preset").json()

    assert applied["current_version"]["version_no"] == edited["version_no"] + 1
    assert applied["current_version"]["model_binding_json"] == edited["model_binding_json"]
    assert applied["preset"]["up_to_date"] is True

    again = client.post(f"/api/agents/{agent['id']}/apply-preset")
    assert again.status_code == 400
    assert "已是最新" in again.json()["detail"]


def test_applying_a_preset_to_an_unknown_agent_is_404(client):
    assert client.post("/api/agents/nope/apply-preset").status_code == 404
