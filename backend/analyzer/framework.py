"""LLM-driven analysis framework definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class FrameworkCategory:
    id: str
    title: str
    description: str
    severity: str


DEFAULT_FRAMEWORK: List[FrameworkCategory] = [
    FrameworkCategory(
        id="mandatory",
        title="废标/强制要求",
        description="任何不满足即会导致废标或严重违规的硬性条款，例如资格条件、资质证书、保证金、唯一品牌等。",
        severity="critical",
    ),
    FrameworkCategory(
        id="scoring",
        title="评分要点",
        description="评标中可加分或影响评分排名的条款，如技术亮点、实施方案、服务承诺、商务让利等。",
        severity="high",
    ),
    FrameworkCategory(
        id="cost",
        title="成本/商务影响",
        description="可能影响成本结构、付款节奏、质保、税费等商务条款。",
        severity="medium",
    ),
    FrameworkCategory(
        id="timeline",
        title="时间计划",
        description="交付节点、里程碑、维护期等时间相关要求。",
        severity="medium",
    ),
    FrameworkCategory(
        id="risks",
        title="风险与建议",
        description="潜在的履约风险、澄清建议或补充注意事项。",
        severity="medium",
    ),
]
