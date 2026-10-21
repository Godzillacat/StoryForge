from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, JSON, String, Text, UniqueConstraint
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


class ModelPrice(IdMixin, TimestampMixin, Base):
    """每百万 token 的单价，按「服务商 + 模型」配置。

    单价是**模型**的属性，不是绑定的属性：放角色卡里的话，同一个模型绑在
    十个智能体上就要填十遍，改一次价得改十处。
    """

    __tablename__ = "model_price"
    __table_args__ = (
        UniqueConstraint("provider_id", "model", name="uq_model_price"),
    )

    provider_id: Mapped[str] = mapped_column(
        ForeignKey("provider.id", ondelete="CASCADE"), index=True
    )
    model: Mapped[str] = mapped_column(String(120))
    input_price: Mapped[float] = mapped_column(Float, default=0.0)
    output_price: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")


class Setting(IdMixin, TimestampMixin, Base):
    """P1a 未使用：全局设置目前存在 ``settings.json``，经 ``app.config`` 读写。

    保留此表是因为它在设计文档的数据模型里（§4.3）。P1a 不读写它，
    以免出现「DB 与 settings.json 两套设置机制」；后续切片若要用，
    必须先决定单一权威来源。
    """

    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value_json: Mapped[Any | None] = mapped_column(JSON, default=None)
