import pytest

settings_mod = pytest.importorskip("bot_moderator.models.settings")

try:
    import importlib
    admin_mod = importlib.import_module("bot_moderator.handlers.admin")
except Exception as exc:  # noqa: BLE001
    pytest.skip(f"не удалось импортировать admin-хендлеры: {exc}", allow_module_level=True)


def test_chat_settings_defaults():
    settings = settings_mod.ChatSettings()
    assert settings.flood.enabled is True
    assert settings.captcha.enabled is True
    assert settings.link_guard.enabled is True
    assert settings.silent_mode.enabled is False


def test_stopwords_default_lists():
    config = settings_mod.StopWordsConfig()
    assert len(config.lists) == 2
    assert config.lists[0].name == "soft"
    assert config.lists[0].action == "delete"
    assert config.lists[1].action == "ban"


def test_stopwords_validator_adds_second_list():
    config = settings_mod.StopWordsConfig.model_validate(
        {
            "enabled": True,
            "lists": [
                {
                    "name": "custom",
                    "words": ["alpha"],
                    "action": "delete",
                    "mute_minutes": 15,
                }
            ],
            "warn_threshold": 3,
        }
    )
    assert len(config.lists) == 2
    assert config.lists[0].name == "custom"
    assert config.lists[1].action == "ban"


def test_parse_stopword_argument_handles_index():
    config = settings_mod.StopWordsConfig()
    index, word, explicit = admin_mod._parse_stopword_argument("2 beta", config)
    assert index == 1
    assert word == "beta"
    assert explicit is True


def test_parse_stopword_argument_without_index():
    config = settings_mod.StopWordsConfig()
    index, word, explicit = admin_mod._parse_stopword_argument("gamma", config)
    assert index == 0
    assert word == "gamma"
    assert explicit is False

