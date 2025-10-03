"""Result helper used by moderation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .actions import ActionType


@dataclass(slots=True)
class ModerationResult:
    actions: list[ActionType] = field(default_factory=list)
    triggered_rules: list[str] = field(default_factory=list)

    def extend(self, other: "ModerationResult" | Iterable[ActionType]) -> None:
        if isinstance(other, ModerationResult):
            self.actions.extend(other.actions)
            self.triggered_rules.extend(other.triggered_rules)
        else:
            self.actions.extend(other)

    def add(self, action: ActionType, rule: str | None = None) -> None:
        self.actions.append(action)
        if rule:
            self.triggered_rules.append(rule)
