from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Provider(IdMixin, TimestampMixin, Base):
    """服务商接入信息。密钥明文不进这张表，只留 api_key_ref（D-01）。"""

    __tablename__ = "provider"

    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(60), default="custom")
    base_url: Mapped[str] = mapped_column(String(500), default="")
    api_key_ref: Mapped[str] = mapped_column(String(120), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(default=0)


class Setting(IdMixin, TimestampMixin, Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value_json: Mapped[Any | None] = mapped_column(JSON, default=None)
