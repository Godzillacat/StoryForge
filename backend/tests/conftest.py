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
    from app.db import session as db_session

    db_session.init_db()
    with db_session.SessionLocal() as s:
        yield s
