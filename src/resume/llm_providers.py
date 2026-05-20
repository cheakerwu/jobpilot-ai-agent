"""
大模型提供商抽象接口
"""
from abc import ABC, abstractmethod
from collections.abc import Generator
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

    def generate_stream(self, prompt: str) -> Generator[str, None, None]:
        """流式生成文本。默认回退到一次性生成。"""
        yield self.generate(prompt)


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
        max_tokens = self.max_tokens if self.max_tokens is not None else 4096
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_stream(self, prompt: str) -> Generator[str, None, None]:
        max_tokens = self.max_tokens if self.max_tokens is not None else 4096
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text


class _OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI 兼容格式的 Provider 基类（OpenAI / DeepSeek / Qwen / 自定义代理）"""

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int | None = 2000,
        base_url: str = "https://api.openai.com/v1",
        request_timeout: int = 90,
        **kwargs,
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.base_url = base_url
        self.request_timeout = request_timeout
        self._extra_body = {}
        if kwargs.get("enable_thinking"):
            self._extra_body["enable_thinking"] = True

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, prompt: str, stream: bool = False) -> dict:
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }
        if self.max_tokens is not None:
            data["max_tokens"] = self.max_tokens
        if self._extra_body:
            data.update(self._extra_body)
        return data

    @retry(max_attempts=3, delay=2, exceptions=(Exception,))
    def generate(self, prompt: str) -> str:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=self._payload(prompt, stream=False),
            timeout=self.request_timeout,
        )
        _raise_for_status(response)
        return response.json()["choices"][0]["message"]["content"]

    def generate_stream(self, prompt: str) -> Generator[str, None, None]:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=self._payload(prompt, stream=True),
            timeout=self.request_timeout,
            stream=True,
        )
        _raise_for_status(response)
        for line in response.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8")
            if not decoded.startswith("data: "):
                continue
            data_str = decoded[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                import json
                chunk = json.loads(data_str)
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
            except (json.JSONDecodeError, KeyError, IndexError):
                continue


class OpenAIProvider(_OpenAICompatibleProvider):
    """OpenAI API 提供商"""

    def __init__(self, api_key: str, model: str = "gpt-4o", max_tokens: int | None = 2000,
                 base_url: str = None, request_timeout: int = 90, **kwargs):
        super().__init__(api_key=api_key, model=model, max_tokens=max_tokens,
                         base_url=base_url or "https://api.openai.com/v1",
                         request_timeout=request_timeout, **kwargs)


class DeepSeekProvider(_OpenAICompatibleProvider):
    """DeepSeek API 提供商（兼容 OpenAI 格式）"""

    def __init__(self, api_key: str, model: str = "deepseek-chat", max_tokens: int | None = 2000,
                 request_timeout: int = 90, **kwargs):
        super().__init__(api_key=api_key, model=model, max_tokens=max_tokens,
                         base_url="https://api.deepseek.com/v1",
                         request_timeout=request_timeout, **kwargs)


class QwenProvider(_OpenAICompatibleProvider):
    """阿里云百炼 Qwen API 提供商（兼容 OpenAI 格式）"""

    def __init__(self, api_key: str, model: str = "qwen3.5-plus", max_tokens: int | None = 2000,
                 enable_thinking: bool = False, base_url: str = None, request_timeout: int = 90, **kwargs):
        super().__init__(api_key=api_key, model=model, max_tokens=max_tokens,
                         base_url=base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                         request_timeout=request_timeout,
                         enable_thinking=enable_thinking, **kwargs)


class MimoProvider(_OpenAICompatibleProvider):
    """小米 MiMo API 提供商（兼容 OpenAI 格式）"""

    def __init__(self, api_key: str, model: str = "MiMo-v2.5-Pro", max_tokens: int | None = 4096,
                 base_url: str = None, request_timeout: int = 120, **kwargs):
        super().__init__(api_key=api_key, model=model, max_tokens=max_tokens,
                         base_url=base_url or "https://token-plan-cn.xiaomimimo.com/v1",
                         request_timeout=request_timeout, **kwargs)


def create_llm_provider(provider_type: str, api_key: str, config: dict) -> BaseLLMProvider:
    """工厂函数：创建 LLM 提供商实例"""
    providers = {
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
        "deepseek": DeepSeekProvider,
        "qwen": QwenProvider,
        "mimo": MimoProvider,
    }

    provider_class = providers.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"不支持的模型提供商: {provider_type}")

    signature = inspect.signature(provider_class.__init__)
    allowed = set(signature.parameters) - {"self", "api_key"}
    filtered_config = {key: value for key, value in config.items() if key in allowed}
    return provider_class(api_key=api_key, **filtered_config)
