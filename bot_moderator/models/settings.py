"""Chat-level configuration models."""

from __future__ import annotations

from datetime import time
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SilentModeConfig(BaseModel):
    enabled: bool = False
    suppress_events: set[str] = Field(default_factory=lambda: {
        "ban",
        "mute",
        "warning",
        "stop_words",
        "profanity",
        "captcha",
        "join_block",
    })


class FloodProtectionConfig(BaseModel):
    enabled: bool = True
    message_limit: int = 6
    interval_seconds: int = 10
    punishment: Literal["mute", "ban", "delete"] = "mute"
    mute_minutes: int = 360


class ProfanityConfig(BaseModel):
    enabled: bool = False
    warn_threshold: int = 2
    mute_minutes: int = 60
    dictionary: list[str] = Field(default_factory=list)


class LinkGuardConfig(BaseModel):
    enabled: bool = True
    allow_trusted: bool = True
    block_all: bool = False
    whitelist_domains: list[str] = Field(default_factory=list)
    blacklist_domains: list[str] = Field(default_factory=list)
    trust_user_ids: set[int] = Field(default_factory=set)


class StopWordListConfig(BaseModel):
    name: str = "default"
    words: list[str] = Field(default_factory=list)
    action: Literal["delete", "mute", "ban"] = "delete"
    mute_minutes: int = 120





def _default_stopword_lists() -> list["StopWordListConfig"]:
    return [
        StopWordListConfig(name="soft", action="delete"),
        StopWordListConfig(name="strict", action="ban"),
    ]


class StopWordsConfig(BaseModel):
    enabled: bool = False
    lists: list[StopWordListConfig] = Field(default_factory=_default_stopword_lists)
    warn_threshold: int = 2

    @model_validator(mode="after")
    def _ensure_lists(cls, value: "StopWordsConfig") -> "StopWordsConfig":
        if not value.lists:
            value.lists = _default_stopword_lists()
        elif len(value.lists) == 1:
            value.lists.append(StopWordListConfig(name="strict", action="ban"))
        return value


class NightModeConfig(BaseModel):
    enabled: bool = False
    start: time = time(hour=0, minute=0)
    end: time = time(hour=6, minute=0)
    action: Literal["delete", "mute"] = "delete"


class SystemMessagesConfig(BaseModel):
    delete_join: bool = True
    delete_leave: bool = True
    delete_pinned: bool = False


class ChannelMessagesConfig(BaseModel):
    allow_from_linked: bool = True
    blocked_channel_ids: set[int] = Field(default_factory=set)


class CaptchaConfig(BaseModel):
    enabled: bool = True
    type: Literal["button", "math"] = "button"
    timeout_seconds: int = 120
    max_attempts: int = 2
    welcome_immunity_minutes: int = 10


class WelcomeButton(BaseModel):
    title: str
    url: str


class WelcomeConfig(BaseModel):
    enabled: bool = True
    text: str = (
        "Привет, {user}! Добро пожаловать в {chat}. Пожалуйста, ознакомьтесь с правилами и ведите себя уважительно."
    )
    buttons: list[WelcomeButton] = Field(default_factory=list)
    delete_after_seconds: int | None = None


class ReportsConfig(BaseModel):
    enabled: bool = True
    destination_chat_id: int | None = None
    include_actions: bool = True


class CrossBanConfig(BaseModel):
    enabled: bool = False
    network_token: str | None = None
    auto_share: bool = True


class ForwardingConfig(BaseModel):
    allow_external_forwards: bool = False
    allow_channel_forwards: bool = False
    whitelist_senders: set[int] = Field(default_factory=set)


class VotingConfig(BaseModel):
    enabled: bool = True
    duration_minutes: int = 15
    votes_required: int = 5
    allow_admin_override: bool = True


class WarningConfig(BaseModel):
    enabled: bool = True
    max_warnings: int = 3
    punish_action: Literal["mute", "ban"] = "mute"
    mute_minutes: int = 60


class ReputationConfig(BaseModel):
    enabled: bool = True
    positive_keywords: list[str] = Field(
        default_factory=lambda: ["спасибо", "благодарю", "+", "👍", "👏"]
    )
    negative_keywords: list[str] = Field(default_factory=lambda: ["-", "👎"])
    upvote_command: str = "+rep"
    downvote_command: str = "-rep"
    daily_limit: int = 5


class FirstCommentGuardConfig(BaseModel):
    enabled: bool = False
    window_seconds: int = 60


class RulesConfig(BaseModel):
    text: str = ""
    buttons: list[WelcomeButton] = Field(default_factory=list)
    post_as_comment: bool = False


class CommentCloserConfig(BaseModel):
    enabled: bool = False
    keywords: list[str] = Field(default_factory=list)


class AntiRaidConfig(BaseModel):
    enabled: bool = True
    join_threshold: int = 5
    within_seconds: int = 60
    action: Literal["mute", "ban", "captcha"] = "mute"


class JoinFilterConfig(BaseModel):
    enabled: bool = True
    presets: list[str] = Field(default_factory=list)
    name_stopwords: list[str] = Field(default_factory=list)
    close_chat: bool = False


class QuestionnaireConfig(BaseModel):
    enabled: bool = False
    questions: list[str] = Field(default_factory=list)
    auto_reject_seconds: int = 180


class SubscriptionConfig(BaseModel):
    tier: Literal["free", "premium"] = "free"
    expires_at: int | None = None


class ChatSettings(BaseModel):
    language: Literal["ru", "en"] = "ru"
    timezone: str = "Europe/Moscow"
    silent_mode: SilentModeConfig = Field(default_factory=SilentModeConfig)
    flood: FloodProtectionConfig = Field(default_factory=FloodProtectionConfig)
    profanity: ProfanityConfig = Field(default_factory=ProfanityConfig)
    link_guard: LinkGuardConfig = Field(default_factory=LinkGuardConfig)
    stop_words: StopWordsConfig = Field(default_factory=StopWordsConfig)
    night_mode: NightModeConfig = Field(default_factory=NightModeConfig)
    system_messages: SystemMessagesConfig = Field(default_factory=SystemMessagesConfig)
    channel_messages: ChannelMessagesConfig = Field(default_factory=ChannelMessagesConfig)
    captcha: CaptchaConfig = Field(default_factory=CaptchaConfig)
    welcome: WelcomeConfig = Field(default_factory=WelcomeConfig)
    reports: ReportsConfig = Field(default_factory=ReportsConfig)
    crossban: CrossBanConfig = Field(default_factory=CrossBanConfig)
    forwards: ForwardingConfig = Field(default_factory=ForwardingConfig)
    voting: VotingConfig = Field(default_factory=VotingConfig)
    warnings: WarningConfig = Field(default_factory=WarningConfig)
    reputation: ReputationConfig = Field(default_factory=ReputationConfig)
    first_comment_guard: FirstCommentGuardConfig = Field(default_factory=FirstCommentGuardConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    comment_closer: CommentCloserConfig = Field(default_factory=CommentCloserConfig)
    anti_raid: AntiRaidConfig = Field(default_factory=AntiRaidConfig)
    join_filter: JoinFilterConfig = Field(default_factory=JoinFilterConfig)
    questionnaire: QuestionnaireConfig = Field(default_factory=QuestionnaireConfig)
    subscription: SubscriptionConfig = Field(default_factory=SubscriptionConfig)

    def is_premium(self) -> bool:
        return self.subscription.tier == "premium"


DEFAULT_SETTINGS = ChatSettings()
