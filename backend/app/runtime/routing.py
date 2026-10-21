"""模型分路解析。

纯函数：决定这次调用用哪家服务商、哪个模型、哪一档参数。不碰数据库，
也不依赖 FastAPI —— 分路的全部规则都能被 pytest 直接钉住。

分路按**任务类型**配置，不按智能体：任务类型是作者心里的概念
（「正文用哪个模型」），智能体是它的实现。
"""

from __future__ import annotations

from dataclasses import dataclass, field

_DEFAULT_PROFILE = "balanced"

# 版本上的参数档默认就是 balanced；把它当成「作者没意见」，
# 否则分路里的参数档永远轮不到生效。
_IMPLICIT_PROFILE = "balanced"


@dataclass(frozen=True)
class RoutingResult:
    binding: dict
    profile: str
    warnings: list[str] = field(default_factory=list)


def normalize_routing_entry(value) -> dict:
    """分路值应当是对象；手改 settings.json 写成字符串时按「只配了模型」理解。"""
    if isinstance(value, str):
        text = value.strip()
        return {"model": text} if text else {}
    if isinstance(value, dict):
        return dict(value)
    return {}


def resolve_binding(
    *,
    version_binding: dict | None,
    version_profile: str | None,
    task_type: str,
    routing: dict | None,
    default_model: str | None,
) -> RoutingResult:
    """逐字段补齐：角色卡显式绑定 > 任务分路 > 全局默认。

    逐字段而不是整体回落，是为了让「只换模型、服务商跟随分路」这类最常见的
    组合不必把分路配两遍。
    """
    version = dict(version_binding or {})
    route = normalize_routing_entry((routing or {}).get(task_type))
    warnings: list[str] = []

    binding: dict = {}

    provider_id = version.get("provider_id") or route.get("provider_id")
    if provider_id:
        binding["provider_id"] = provider_id

    model = version.get("model") or route.get("model") or default_model
    if model:
        binding["model"] = model

    profile = version_profile or ""
    if profile and profile != _IMPLICIT_PROFILE:
        pass  # 作者显式改过，保持
    else:
        profile = route.get("param_profile") or profile or _DEFAULT_PROFILE

    return RoutingResult(binding=binding, profile=profile, warnings=warnings)
