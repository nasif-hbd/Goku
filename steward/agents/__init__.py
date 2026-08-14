"""The agent roster.

Order matters: chase and collections generate the activity, reports and risk
interpret it, and digest reports on all of them - so digest runs last.
"""

from .base import Agent, TickContext, run_all
from .chase import ChaseAgent
from .collections import CollectionAgent
from .digest import DigestAgent
from .reports import ReportAgent
from .risk import RiskAgent


def default_roster() -> list[Agent]:
    return [
        ChaseAgent(),
        CollectionAgent(),
        ReportAgent(),
        RiskAgent(),
        DigestAgent(),
    ]


__all__ = [
    "Agent",
    "TickContext",
    "run_all",
    "ChaseAgent",
    "CollectionAgent",
    "DigestAgent",
    "ReportAgent",
    "RiskAgent",
    "default_roster",
]
