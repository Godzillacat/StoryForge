from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SearchIndexState(Base):
    """每个项目一行的检索索引状态；没有行等价于需要重建。"""

    __tablename__ = "search_index_state"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dirty: Mapped[int] = mapped_column(Integer, default=1)
    schema_version: Mapped[int] = mapped_column(Integer, default=0)
    rebuilt_at: Mapped[str | None] = mapped_column(Text, default=None)
