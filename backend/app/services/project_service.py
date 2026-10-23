from __future__ import annotations

import shutil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.db.models import Project
from app.services import search_service


def list_projects(session: Session) -> list[Project]:
    return list(session.scalars(select(Project).order_by(Project.created_at.desc())))


def create_project(session: Session, **fields) -> Project:
    project = Project(**fields)
    session.add(project)
    session.commit()
    return project


def get_project(session: Session, project_id: str) -> Project | None:
    return session.get(Project, project_id)


def update_project(session: Session, project_id: str, **fields) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    for key, value in fields.items():
        if value is not None:
            setattr(project, key, value)
    session.commit()
    return project


def delete_project(session: Session, project_id: str) -> None:
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"项目不存在：{project_id}")
    search_service.delete_project(session, project_id)
    session.delete(project)
    session.commit()
    # 资产目录跟着项目走：库里的行没了，磁盘上的封面与附件不该留下无主文件。
    # 用 project.id（库里那条）而不是请求里的 project_id；路径也只从
    # project_assets_dir 这一处来 —— 存储布局不该有第二份定义。
    # 注意它在目录不存在时会建出一个空的，所以这里只删已存在的。
    assets = config.project_assets_dir(project.id)
    if assets.is_dir() and not any(assets.iterdir()):
        assets.rmdir()
    else:
        shutil.rmtree(assets, ignore_errors=True)
