import pytest
from sqlalchemy import select

from app.db.models import (
    Pipeline,
    PipelineNode,
    PipelineRun,
    PipelineRunNode,
    Project,
)


def _project(session, name="雾港"):
    project = Project(name=name)
    session.add(project)
    session.commit()
    return project


def test_pipeline_defaults(session):
    project = _project(session)
    pipeline = Pipeline(project_id=project.id)
    session.add(pipeline)
    session.commit()

    assert pipeline.policy == "key_only"


def test_project_id_is_unique(session):
    project = _project(session)
    session.add(Pipeline(project_id=project.id))
    session.commit()
    session.add(Pipeline(project_id=project.id))

    with pytest.raises(Exception):
        session.commit()
    session.rollback()


def test_deleting_project_cascades_to_pipeline_and_runs(session):
    project = _project(session)
    pipeline = Pipeline(project_id=project.id)
    session.add(pipeline)
    session.commit()
    session.add(PipelineNode(pipeline_id=pipeline.id, seq=0, name="解析", task_type="idea_parse"))
    session.add(PipelineRun(project_id=project.id, pipeline_id=pipeline.id))
    session.commit()

    session.delete(session.get(Project, project.id))
    session.commit()

    assert session.query(Pipeline).count() == 0
    assert session.query(PipelineNode).count() == 0
    assert session.query(PipelineRun).count() == 0


def test_deleting_pipeline_cascades_to_nodes_but_not_runs(session):
    project = _project(session)
    pipeline = Pipeline(project_id=project.id)
    session.add(pipeline)
    session.commit()
    session.add(PipelineNode(pipeline_id=pipeline.id, seq=0, name="解析", task_type="idea_parse"))
    run = PipelineRun(project_id=project.id, pipeline_id=pipeline.id)
    session.add(run)
    session.commit()

    session.delete(session.get(Pipeline, pipeline.id))
    session.commit()

    assert session.query(PipelineNode).count() == 0
    # 历史运行不该因为管线被删而消失
    assert session.query(PipelineRun).count() == 1


def test_deleting_run_cascades_to_run_nodes(session):
    project = _project(session)
    run = PipelineRun(project_id=project.id)
    session.add(run)
    session.commit()
    session.add(PipelineRunNode(run_id=run.id, seq=0, name="解析", task_type="idea_parse"))
    session.commit()

    session.delete(session.get(PipelineRun, run.id))
    session.commit()

    assert session.query(PipelineRunNode).count() == 0


def test_run_and_node_defaults(session):
    project = _project(session)
    run = PipelineRun(project_id=project.id)
    session.add(run)
    session.commit()
    node = PipelineRunNode(run_id=run.id, seq=0, name="解析", task_type="idea_parse")
    session.add(node)
    session.commit()

    assert run.status == "paused"
    assert run.cursor == 0
    assert run.message == ""
    assert node.status == "pending"
    assert node.summary_json == {}


def test_nodes_are_ordered_by_seq(session):
    project = _project(session)
    pipeline = Pipeline(project_id=project.id)
    session.add(pipeline)
    session.commit()
    session.add_all(
        [
            PipelineNode(pipeline_id=pipeline.id, seq=1, name="二", task_type="architecture"),
            PipelineNode(pipeline_id=pipeline.id, seq=0, name="一", task_type="idea_parse"),
        ]
    )
    session.commit()

    nodes = session.scalars(
        select(PipelineNode)
        .where(PipelineNode.pipeline_id == pipeline.id)
        .order_by(PipelineNode.seq)
    ).all()

    assert [n.name for n in nodes] == ["一", "二"]
