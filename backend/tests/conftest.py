import os
import tempfile

import pytest

# 必须在导入 app.* 之前设好，engine 在 import 时就会读数据目录
_TMP = tempfile.mkdtemp(prefix="storyforge-test-")
os.environ["STORYFORGE_DATA_DIR"] = _TMP


@pytest.fixture(scope="session")
def data_dir_path():
    from app import config

    return config.data_dir()


@pytest.fixture()
def session():
    """每个测试一套干净的表。

    不留跨用例的状态：seed_agents 之类「按名字去重」的逻辑一旦被前一个
    用例写过的同名数据撞上，就会静默少建 —— 测出来的是污染，不是行为。
    """
    from app.db import session as db_session
    from app.db.base import Base

    db_session.init_db()
    Base.metadata.drop_all(db_session.engine)
    Base.metadata.create_all(db_session.engine)

    from app.db.search import clear_search_index

    clear_search_index(db_session.engine)
    with db_session.SessionLocal() as s:
        yield s
    # 用例结束同样清表：否则最后一个用例写下的行会留到「不用本 fixture 的
    # 用例」（如 test_api 的 client，它只在既有库里补种子）—— 那类用例会
    # 读到上一文件遗留的同任务类型智能体，测出来的就不是它们自己的行为。
    Base.metadata.drop_all(db_session.engine)


from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import AgentVersion, Provider
from app.db.session import SessionLocal, init_db
from app.main import app
from app.services.seed_service import seed_agents, seed_tools


@pytest.fixture()
def client():
    from app.db import session as db_session
    from app.db.search import clear_search_index

    init_db()
    clear_search_index(db_session.engine)
    with SessionLocal() as session:
        seed_agents(session)
        seed_tools(session)
        # 跑智能体需要一家启用的服务商，这是产品行为不是测试特例。
        # 这里补上前置条件：真实 HTTP 调用被 _patch_client 替换，密钥留空即可。
        if session.scalars(select(Provider).where(Provider.enabled.is_(True))).first() is None:
            session.add(
                Provider(
                    name="测试服务商",
                    kind="custom",
                    base_url="https://api.example.com/v1",
                    enabled=True,
                )
            )
            session.commit()
        # 跑智能体同样需要智能体自身绑定了模型：运行时不再把服务商显示名
        # 当模型 ID 回落，没绑就会在解析阶段报错。预置阵容出厂不带模型名，
        # 由作者在工作室里指定 —— 这里替测试补上这个前置条件。
        for version in session.scalars(select(AgentVersion)):
            binding = dict(version.model_binding_json or {})
            if not binding.get("model"):
                version.model_binding_json = {**binding, "model": "test-model"}
                session.commit()
    with TestClient(app) as c:
        yield c
