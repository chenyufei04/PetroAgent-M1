"""验证 Ollama 适配器使用本地原生 API 和受控 JSON 模式。"""

import json

from petro_agent.llm import provider


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps({"message": {"content": '{"answer":"ok","sections":["rules"]}'}}).encode()


def test_ollama_provider_uses_native_chat_json_mode(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(provider, "urlopen", fake_urlopen)
    settings = provider.LlmSettings(provider="ollama", model="qwen3:8b", base_url="http://localhost:11434")

    result = provider.create_provider(settings).generate_json([{"role": "user", "content": "规则"}])

    assert result["sections"] == ["rules"]
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["body"]["model"] == "qwen3:8b"
    assert captured["body"]["format"] == "json"
    assert captured["body"]["think"] is False


def test_create_provider_keeps_openai_compatible_as_optional_backend() -> None:
    settings = provider.LlmSettings(provider="vllm")

    assert isinstance(provider.create_provider(settings), provider.OpenAICompatibleProvider)
