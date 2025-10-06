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

def test_command_menu_defaults():
    settings = settings_mod.ChatSettings()
    assert settings.command_menu.hidden is False
    assert settings.command_menu.backup_commands == []


def test_reports_defaults():
    reports = settings_mod.ChatSettings().reports
    assert reports.include_rules == set()
    assert reports.exclude_rules == set()
    assert reports.notify_admins is False
    assert reports.secondary_chat_id is None


def test_questionnaire_defaults():
    questionnaire = settings_mod.ChatSettings().questionnaire
    assert questionnaire.auto_reject_seconds == 180
    assert questionnaire.auto_approve_seconds is None

