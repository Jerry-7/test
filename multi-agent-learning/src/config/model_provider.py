from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderPreset:
    """提供方预设。

    这个类描述“某个模型提供方默认怎么接入”：
    - 用哪个环境变量读取 API Key
    - 默认模型名是什么
    - 默认 base_url 是什么
    - 有没有额外请求头
    """

    provider: str
    api_key_env: str
    model_env: str
    base_url_env: str
    default_model: str
    default_base_url: str | None = None


@dataclass(frozen=True)
class ModelProviderConfig:
    """运行时真正使用的模型配置。"""

    provider: str
    model_name: str
    api_key: str
    base_url: str | None
    api_key_env: str
    default_headers: dict[str, str] = field(default_factory=dict)


def build_chat_model_kwargs(
    provider_config: ModelProviderConfig,
    *,
    thinking_mode: str = "default",
) -> dict[str, object]:
    """构建 `ChatOpenAI` 需要的通用参数。

    `thinking_mode` 当前只对 `provider=qwen` 生效：
    - `default`: 不显式传递 thinking 配置
    - `on`: `extra_body={"enable_thinking": True}`
    - `off`: `extra_body={"enable_thinking": False}`
    """

    model_kwargs: dict[str, object] = {
        "model": provider_config.model_name,
        "api_key": provider_config.api_key,
        "temperature": 0,
        "stream_usage": True,
    }
    if provider_config.base_url:
        model_kwargs["base_url"] = provider_config.base_url
    if provider_config.default_headers:
        model_kwargs["default_headers"] = provider_config.default_headers

    if provider_config.provider == "qwen" and thinking_mode in {"on", "off"}:
        model_kwargs["extra_body"] = {
            "enable_thinking": thinking_mode == "on"
        }

    return model_kwargs


# 这些预设让项目可以在“同一个 LangChain 入口”下切换不同服务商。
# 当前阶段我们统一通过 OpenAI 兼容接口接入。
PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset(
        provider="openai",
        api_key_env="OPENAI_API_KEY",
        model_env="OPENAI_MODEL",
        base_url_env="OPENAI_BASE_URL",
        default_model="gpt-5-nano",
        default_base_url=None,
    ),
    "openrouter": ProviderPreset(
        provider="openrouter",
        api_key_env="OPENROUTER_API_KEY",
        model_env="OPENROUTER_MODEL",
        base_url_env="OPENROUTER_BASE_URL",
        default_model="qwen/qwen3.6-plus:free",
        default_base_url="https://openrouter.ai/api/v1",
    ),
    "qwen": ProviderPreset(
        provider="qwen",
        api_key_env="DASHSCOPE_API_KEY",
        model_env="QWEN_MODEL",
        base_url_env="QWEN_BASE_URL",
        default_model="qwen-plus-latest",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
    "glm": ProviderPreset(
        provider="glm",
        api_key_env="ZAI_API_KEY",
        model_env="GLM_MODEL",
        base_url_env="GLM_BASE_URL",
        default_model="glm-5",
        default_base_url="https://open.bigmodel.cn/api/paas/v4/",
    ),
}


def get_supported_providers() -> tuple[str, ...]:
    """返回当前支持的 provider 名称。"""

    return tuple(PROVIDER_PRESETS.keys())


def resolve_provider_config(
    provider: str,
    model_name: str | None = None,
    base_url: str | None = None,
) -> ModelProviderConfig:
    """根据 provider + 环境变量解析实际配置。

    优先级如下：
    1. 函数参数
    2. 对应 provider 的环境变量
    3. 代码中的默认值
    """

    normalized = provider.strip().lower()
    if normalized not in PROVIDER_PRESETS:
        supported = ", ".join(get_supported_providers())
        raise ValueError(
            f"Unsupported provider: {provider}. Supported providers: {supported}."
        )

    preset = PROVIDER_PRESETS[normalized]
    resolved_model = model_name or os.getenv(preset.model_env) or preset.default_model
    resolved_base_url = (
        base_url
        or os.getenv(preset.base_url_env)
        or preset.default_base_url
    )
    api_key = os.getenv(preset.api_key_env)
    if not api_key:
        raise RuntimeError(
            f"Missing {preset.api_key_env}. "
            f"Set the API key for provider '{normalized}' before running."
        )

    default_headers = _build_default_headers(normalized)
    return ModelProviderConfig(
        provider=normalized,
        model_name=resolved_model,
        api_key=api_key,
        base_url=resolved_base_url,
        api_key_env=preset.api_key_env,
        default_headers=default_headers,
    )


def build_provider_config_from_runtime_profile(profile) -> ModelProviderConfig:
    normalized = profile.provider.strip().lower()
    if normalized not in PROVIDER_PRESETS:
        supported = ", ".join(get_supported_providers())
        raise ValueError(
            f"Unsupported provider: {profile.provider}. Supported providers: {supported}."
        )

    preset = PROVIDER_PRESETS[normalized]
    return ModelProviderConfig(
        provider=normalized,
        model_name=profile.model_name,
        api_key=profile.api_key,
        base_url=profile.base_url or preset.default_base_url,
        api_key_env="MODEL_PROFILE",
        default_headers=_build_default_headers(normalized),
    )


def _build_default_headers(provider: str) -> dict[str, str]:
    """构建 provider 级别的可选请求头。"""

    if provider != "openrouter":
        return {}

    headers: dict[str, str] = {}

    # OpenRouter 官方文档说明，这两个头是可选的。
    # 配置后，你的应用信息可以出现在 OpenRouter 侧的统计或归因中。
    http_referer = os.getenv("OPENROUTER_HTTP_REFERER")
    openrouter_title = os.getenv("OPENROUTER_X_TITLE")

    if http_referer:
        headers["HTTP-Referer"] = http_referer
    if openrouter_title:
        headers["X-OpenRouter-Title"] = openrouter_title

    return headers
