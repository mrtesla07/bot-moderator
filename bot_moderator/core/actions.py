"""Moderation actions produced by detectors.""" 

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(slots=True)
class ModerationAction:
    kind: str
    payload: dict[str, Any]


@dataclass(slots=True, init=False)
class DeleteMessage(ModerationAction):
    kind: Literal["delete"] = "delete"
    payload: dict[str, Any] | None = None

    def __init__(self, *, message_id: int) -> None:
        super().__setattr__("kind", "delete")
        super().__setattr__("payload", {"message_id": message_id})


@dataclass(slots=True, init=False)
class MuteUser(ModerationAction):
    kind: Literal["mute"] = "mute"
    payload: dict[str, Any]

    def __init__(self, *, user_id: int, until_seconds: int) -> None:
        super().__setattr__("kind", "mute")
        super().__setattr__("payload", {"user_id": user_id, "until_seconds": until_seconds})


@dataclass(slots=True, init=False)
class BanUser(ModerationAction):
    kind: Literal["ban"] = "ban"
    payload: dict[str, Any]

    def __init__(self, *, user_id: int, until_seconds: int | None = None, delete_history_days: int = 0) -> None:
        super().__setattr__("kind", "ban")
        super().__setattr__(
            "payload",
            {
                "user_id": user_id,
                "until_seconds": until_seconds,
                "delete_history_days": delete_history_days,
            },
        )


@dataclass(slots=True, init=False)
class SendMessage(ModerationAction):
    kind: Literal["send_message"] = "send_message"
    payload: dict[str, Any]

    def __init__(self, *, text: str, reply_to: int | None = None, keyboard: Any | None = None) -> None:
        super().__setattr__("kind", "send_message")
        super().__setattr__("payload", {"text": text, "reply_to": reply_to, "keyboard": keyboard})


@dataclass(slots=True, init=False)
class LiftRestrictions(ModerationAction):
    kind: Literal["lift"] = "lift"
    payload: dict[str, Any]

    def __init__(self, *, user_id: int) -> None:
        super().__setattr__("kind", "lift")
        super().__setattr__("payload", {"user_id": user_id})


@dataclass(slots=True, init=False)
class WarnUser(ModerationAction):
    kind: Literal["warn"] = "warn"
    payload: dict[str, Any]

    def __init__(self, *, user_id: int, reason: str) -> None:
        super().__setattr__("kind", "warn")
        super().__setattr__("payload", {"user_id": user_id, "reason": reason})


@dataclass(slots=True, init=False)
class LogAction(ModerationAction):
    kind: Literal["log"] = "log"
    payload: dict[str, Any]

    def __init__(self, *, level: str, message: str, extra: dict[str, Any] | None = None) -> None:
        super().__setattr__("kind", "log")
        super().__setattr__("payload", {"level": level, "message": message, "extra": extra or {}})


@dataclass(slots=True, init=False)
class RestrictUser(ModerationAction):
    kind: Literal["restrict"] = "restrict"
    payload: dict[str, Any]

    def __init__(self, *, user_id: int, permissions: dict[str, Any], until_seconds: int | None = None) -> None:
        super().__setattr__("kind", "restrict")
        super().__setattr__(
            "payload",
            {
                "user_id": user_id,
                "permissions": permissions,
                "until_seconds": until_seconds,
            },
        )


@dataclass(slots=True, init=False)
class ApplyPenalty(ModerationAction):
    kind: Literal["penalty"] = "penalty"
    payload: dict[str, Any]

    def __init__(self, *, user_id: int, reason: str, penalty: str) -> None:
        super().__setattr__("kind", "penalty")
        super().__setattr__("payload", {"user_id": user_id, "reason": reason, "penalty": penalty})


@dataclass(slots=True, init=False)
class CloseTopic(ModerationAction):
    kind: Literal["close_topic"] = "close_topic"
    payload: dict[str, Any]

    def __init__(self, *, message_thread_id: int) -> None:
        super().__setattr__("kind", "close_topic")
        super().__setattr__("payload", {"message_thread_id": message_thread_id})


ActionType = ModerationAction
