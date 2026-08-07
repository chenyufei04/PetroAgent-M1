"""PetroAgent 大模型提供器与受控交互契约。"""

from .provider import LlmSettings, create_provider

__all__ = ["LlmSettings", "create_provider"]
