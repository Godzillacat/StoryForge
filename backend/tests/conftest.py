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
    with db_session.SessionLocal() as s:
        yield s
    # 用例结束同样清表：否则最后一个用例写下的行会留到「不用本 fixture 的
    # 用例」（如 test_api 的 client，它只在既有库里补种子）—— 那类用例会
    # 读到上一文件遗留的同任务类型智能体，测出来的就不是它们自己的行为。
    Base.metadata.drop_all(db_session.engine)
