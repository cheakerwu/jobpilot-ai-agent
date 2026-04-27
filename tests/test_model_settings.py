"""
模型设置与不限选项测试
"""
import yaml
import pytest
from pydantic import ValidationError

from src.resume.generator import ResumeGenerator
from src.resume.llm_providers import OpenAIProvider, DeepSeekProvider, QwenProvider
from web_api.routers import settings
from web_api.routers.settings import ModelSettingsUpdate


def test_model_settings_accepts_unlimited_limits():
    req = ModelSettingsUpdate(
        provider="qwen",
        model="qwen3.5-plus",
        max_tokens=None,
        rate_limit=None,
        daily_limit=None,
    )

    assert req.max_tokens is None
    assert req.rate_limit is None
    assert req.daily_limit is None


def test_model_settings_still_validates_numeric_limits():
    with pytest.raises(ValidationError):
        ModelSettingsUpdate(
            provider="qwen",
            model="qwen3.5-plus",
            max_tokens=128,
        )


@pytest.mark.asyncio
async def test_update_model_settings_persists_unlimited_limits(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    initial_config = {
        "profile_path": "config/user_profile.json",
        "resume": {
            "provider": "qwen",
            "model": "qwen3.5-plus",
            "max_tokens": 2000,
            "rate_limit": 10,
            "daily_limit": 10,
        },
        "storage": {"db_path": "data/jobs.db"},
    }

    def fake_load_config():
        if config_path.exists():
            return yaml.safe_load(config_path.read_text(encoding="utf-8"))
        return initial_config

    monkeypatch.setattr(settings, "CONFIG_PATH", config_path)
    monkeypatch.setattr(settings, "load_config", fake_load_config)

    response = await settings.update_model_settings(ModelSettingsUpdate(
        provider="qwen",
        model="qwen3.5-plus",
        max_tokens=None,
        rate_limit=None,
        daily_limit=None,
    ))
    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert response["success"] is True
    assert saved["resume"]["max_tokens"] is None
    assert saved["resume"]["rate_limit"] is None
    assert saved["resume"]["daily_limit"] is None
    assert response["current"]["max_tokens"] is None


@pytest.mark.parametrize("provider_cls", [OpenAIProvider, DeepSeekProvider, QwenProvider])
def test_openai_compatible_providers_omit_max_tokens_when_unlimited(provider_cls, monkeypatch):
    captured_payloads = []
    captured_timeouts = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}]}

    def fake_post(url, headers, json, timeout):
        captured_payloads.append(json)
        captured_timeouts.append(timeout)
        return FakeResponse()

    monkeypatch.setattr("src.resume.llm_providers.requests.post", fake_post)

    provider = provider_cls(api_key="test-key", max_tokens=None, request_timeout=90)
    provider.generate("hello")

    assert "max_tokens" not in captured_payloads[0]
    assert captured_timeouts[0] == 90


def test_qwen_uses_china_endpoint_by_default():
    provider = QwenProvider(api_key="test-key", model="qwen3.6-flash")

    assert provider.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_qwen_base_url_can_be_overridden():
    provider = QwenProvider(
        api_key="test-key",
        model="qwen3.6-flash",
        base_url="https://example.test/v1",
    )

    assert provider.base_url == "https://example.test/v1"


def test_resume_generator_skips_rate_limit_when_unlimited():
    class DummyLLM:
        def generate(self, prompt):
            return "{}"

    generator = ResumeGenerator(DummyLLM(), {"rate_limit": None, "cache_enabled": False})
    generator._check_rate_limit()

    assert generator._call_times == []
