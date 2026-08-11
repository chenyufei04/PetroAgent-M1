"""提供可替换的大模型访问层，默认无需 GPU 即可用 Mock 完成页面调试。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class LlmSettings:
    """本地模型服务配置；当前默认运行时为 Ollama，密钥只从环境变量读取。"""

    provider: str = "mock"
    base_url: str = "http://127.0.0.1:11434"
    api_key: str = "ollama"
    model: str = "qwen3:8b"
    timeout_seconds: int = 120
    temperature: float = 0.4

    @classmethod
    def from_env(cls) -> "LlmSettings":
        return cls(
            provider=os.getenv("PETRO_AGENT_LLM_PROVIDER", "mock").strip().lower(),
            base_url=os.getenv("PETRO_AGENT_LLM_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
            api_key=os.getenv("PETRO_AGENT_LLM_API_KEY", "ollama"),
            model=os.getenv("PETRO_AGENT_LLM_MODEL", "qwen3:8b"),
            timeout_seconds=int(os.getenv("PETRO_AGENT_LLM_TIMEOUT_SECONDS", "120")),
            temperature=float(os.getenv("PETRO_AGENT_LLM_TEMPERATURE", "0.4")),
        )


class LlmProvider(Protocol):
    """统一文本生成接口，便于日后替换 Qwen、云端模型或测试替身。"""

    name: str

    def generate_json(self, messages: list[dict[str, str]]) -> dict[str, Any]: ...


class MockProvider:
    """离线调试提供器：不伪造工程数值，只返回 Agent 已检索到的事实摘要。"""

    name = "mock"

    def generate_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        context = json.loads(messages[-1]["content"])
        return {
            "answer": context["draft_answer"],
            "sections": context["suggested_sections"],
            "selected_case_id": context.get("selected_case_id"),
        }


class OpenAICompatibleProvider:
    """调用 vLLM 暴露的 OpenAI-compatible Chat Completions 接口。"""

    name = "openai-compatible"

    def __init__(self, settings: LlmSettings):
        self.settings = settings

    def generate_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": self.settings.temperature,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
            # 工程解释优先稳定、简洁，不向页面泄露模型内部推理过程。
            "chat_template_kwargs": {"enable_thinking": False},
        }
        request = Request(
            f"{self.settings.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.settings.api_key}"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f"Qwen 服务不可用：{exc}") from exc
        content = result["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Qwen 未返回约定的 JSON 对象") from exc


class OllamaProvider:
    """调用 Ollama 原生 Chat API，使用 JSON 模式约束页面展示指令。"""

    name = "ollama"

    def __init__(self, settings: LlmSettings):
        self.settings = settings

    def generate_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "think": False,
            "options": {"temperature": self.settings.temperature, "num_predict": 1200},
        }
        request = Request(
            f"{self.settings.base_url}/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f"Ollama 服务不可用：{exc}") from exc
        content = result.get("message", {}).get("content", "")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama/Qwen 未返回约定的 JSON 对象") from exc


def create_provider(settings: LlmSettings | None = None) -> LlmProvider:
    settings = settings or LlmSettings.from_env()
    if settings.provider == "mock":
        return MockProvider()
    if settings.provider == "ollama":
        return OllamaProvider(settings)
    if settings.provider in {"qwen", "vllm", "openai-compatible"}:
        return OpenAICompatibleProvider(settings)
    raise ValueError(f"不支持的大模型提供器：{settings.provider}")
