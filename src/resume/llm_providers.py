"""
大模型提供商抽象接口
"""
from abc import ABC, abstractmethod
from anthropic import Anthropic
import requests
import inspect
from ..utils.retry import retry


def _raise_for_status(response):
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        body = response.text[:800] if response.text else ""
        raise requests.HTTPError(f"{e}; response={body}", response=response) from e


class BaseLLMProvider(ABC):
    """大模型提供商基类"""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """生成文本"""
        pass


class ClaudeProvider(BaseLLMProvider):
    """Claude API 提供商"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int | None = 2000,
        request_timeout: int = 90,
    ):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.request_timeout = request_timeout

    @retry(max_attempts=3, delay=2, exceptions=(Exception,))
    def generate(self, prompt: str) -> str:
        # Anthropic Messages API requires max_tokens, even when app-side cap is disabled.
        max_tokens = self.max_tokens if self.max_tokens is not None else 4096
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API 提供商"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        max_tokens: int | None = 2000,
        base_url: str = None,
        request_timeout: int = 90,
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.base_url = base_url or "https://api.openai.com/v1"
        self.request_timeout = request_timeout

    @retry(max_attempts=3, delay=2, exceptions=(Exception,))
    def generate(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.max_tokens is not None:
            data["max_tokens"] = self.max_tokens
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=self.request_timeout,
        )
        _raise_for_status(response)
        return response.json()["choices"][0]["message"]["content"]


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API 提供商（兼容 OpenAI 格式）"""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        max_tokens: int | None = 2000,
        request_timeout: int = 90,
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.base_url = "https://api.deepseek.com/v1"
        self.request_timeout = request_timeout

    @retry(max_attempts=3, delay=2, exceptions=(Exception,))
    def generate(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.max_tokens is not None:
            data["max_tokens"] = self.max_tokens
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=self.request_timeout,
        )
        _raise_for_status(response)
        return response.json()["choices"][0]["message"]["content"]


class QwenProvider(BaseLLMProvider):
    """阿里云百炼 Qwen API 提供商（兼容 OpenAI 格式）"""

    def __init__(
        self,
        api_key: str,
        model: str = "qwen3.5-plus",
        max_tokens: int | None = 2000,
        enable_thinking: bool = False,
        base_url: str = None,
        request_timeout: int = 90,
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking
        self.base_url = base_url or self._default_base_url(model)
        self.request_timeout = request_timeout

    def _default_base_url(self, model: str) -> str:
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"

    @retry(max_attempts=3, delay=2, exceptions=(Exception,))
    def generate(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.max_tokens is not None:
            data["max_tokens"] = self.max_tokens
        # 如果启用深度思考功能
        if self.enable_thinking:
            data["extra_body"] = {"enable_thinking": True}

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=self.request_timeout,
        )
        _raise_for_status(response)
        return response.json()["choices"][0]["message"]["content"]


def create_llm_provider(provider_type: str, api_key: str, config: dict) -> BaseLLMProvider:
    """工厂函数：创建 LLM 提供商实例"""
    providers = {
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
        "deepseek": DeepSeekProvider,
        "qwen": QwenProvider,
    }

    provider_class = providers.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"不支持的模型提供商: {provider_type}")

    signature = inspect.signature(provider_class.__init__)
    allowed = set(signature.parameters) - {"self", "api_key"}
    filtered_config = {key: value for key, value in config.items() if key in allowed}
    return provider_class(api_key=api_key, **filtered_config)
