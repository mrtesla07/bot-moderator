import pytest

settings_mod = pytest.importorskip("bot_moderator.models.settings")


def test_chat_settings_defaults():
    settings = settings_mod.ChatSettings()
    assert settings.flood.enabled is True
    assert settings.captcha.enabled is True
    assert settings.link_guard.enabled is True
    assert settings.silent_mode.enabled is False
