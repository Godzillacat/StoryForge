from app.agents.roster import TASK_TYPE_LABELS, task_type_label
from app.db.models import Agent, AgentVersion, GenerationRun, ModelPrice, Project, Provider
from app.services import provider_service


def _seed(session):
    project = Project(name="雾港")
    provider = Provider(name="百炼", base_url="https://api.example.com/v1")
    session.add_all([project, provider])
    session.commit()

    writer = Agent(name="执笔", task_type="write")
    auditor = Agent(name="审校", task_type="continuity")
    session.add_all([writer, auditor])
    session.commit()

    writer_version = AgentVersion(
        agent_id=writer.id, version_no=1, model_binding_json={"model": "m-priced"}
    )
    auditor_version = AgentVersion(
        agent_id=auditor.id, version_no=1, model_binding_json={"model": "m-unpriced"}
    )
    session.add_all([writer_version, auditor_version])
    session.commit()
    writer.current_version_id = writer_version.id
    auditor.current_version_id = auditor_version.id
    session.commit()

    session.add(
        ModelPrice(
            provider_id=provider.id, model="m-priced", input_price=2.0, output_price=8.0
        )
    )
    session.add_all(
        [
            GenerationRun(
                project_id=project.id,
                agent_id=writer.id,
                agent_version_id=writer_version.id,
                provider_id=provider.id,
                model="m-priced",
                prompt_tokens=100,
                completion_tokens=50,
                cost_estimate=0.0006,
            ),
            GenerationRun(
                project_id=project.id,
                agent_id=writer.id,
                agent_version_id=writer_version.id,
                provider_id=provider.id,
                model="m-priced",
                prompt_tokens=200,
                completion_tokens=100,
                cost_estimate=0.0012,
            ),
            GenerationRun(
                project_id=project.id,
                agent_id=auditor.id,
                agent_version_id=auditor_version.id,
                provider_id=provider.id,
                model="m-unpriced",
                prompt_tokens=10,
                completion_tokens=5,
                cost_estimate=0.0,
            ),
        ]
    )
    session.commit()
    return project, provider, writer, auditor


def test_legacy_fields_are_unchanged(session):
    project, *_ = _seed(session)

    summary = provider_service.project_cost_summary(session, project.id)

    assert summary["runs"] == 3
    assert summary["prompt_tokens"] == 310
    assert summary["completion_tokens"] == 155
    assert summary["cost_estimate"] == 0.0018


def test_groups_by_agent(session):
    project, _provider, writer, auditor = _seed(session)

    summary = provider_service.project_cost_summary(session, project.id)

    rows = {row["agent_id"]: row for row in summary["by_agent"]}
    assert rows[writer.id]["runs"] == 2
    assert rows[writer.id]["prompt_tokens"] == 300
    assert rows[writer.id]["unpriced_runs"] == 0
    assert rows[auditor.id]["runs"] == 1
    assert rows[auditor.id]["unpriced_runs"] == 1


def test_groups_by_task_with_labels(session):
    project, *_ = _seed(session)

    summary = provider_service.project_cost_summary(session, project.id)

    rows = {row["task_type"]: row for row in summary["by_task"]}
    assert rows["write"]["label"] == "正文"
    assert rows["continuity"]["label"] == "审校"
    assert rows["write"]["runs"] == 2


def test_unpriced_runs_counts_only_unpriced_models(session):
    project, *_ = _seed(session)

    summary = provider_service.project_cost_summary(session, project.id)

    assert summary["unpriced_runs"] == 1


def test_binding_prices_count_as_priced(session):
    project, _provider, writer, _auditor = _seed(session)
    version = session.get(AgentVersion, writer.current_version_id)
    version.model_binding_json = {
        "model": "m-priced",
        "prices": {"input": 1.0, "output": 1.0},
    }
    session.commit()
    # 删掉单价行，绑定里的 prices 仍应让这些运行算作已定价
    for row in session.query(ModelPrice).all():
        session.delete(row)
    session.commit()

    summary = provider_service.project_cost_summary(session, project.id)

    assert summary["unpriced_runs"] == 1  # 只剩审校那条


def test_unknown_task_type_falls_back_to_its_key():
    assert task_type_label("polish") == "润色"
    assert task_type_label("something_new") == "something_new"
    assert task_type_label(None) == "未知任务"
    assert "write" in TASK_TYPE_LABELS
