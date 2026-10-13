"""Builds the speech-to-text, LLM and text-to-speech services from .env settings.

Any LLM works in "cascade" mode: the gateway listens (STT), attaches the newest
camera frame to your question, asks the LLM, and speaks the answer (TTS).
Models with native live audio+video (Gemini Live) can use "gemini_live" mode.
"""

import os

from loguru import logger
from pipecat.transcriptions.language import Language


def env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if v not in (None, "") else default


def _lang(code: str | None):
    if not code or code == "auto":
        return None
    try:
        return Language(code)
    except ValueError:
        logger.warning(f"Unknown language '{code}', using auto")
        return None


# OpenAI-compatible endpoints: GLM, Kimi, Llama/Qwen hosts, local Ollama...
COMPATIBLE_BASE_URLS = {
    "glm": "https://open.bigmodel.cn/api/paas/v4",       # Zhipu GLM (vision: glm-4.5v etc.)
    "kimi": "https://api.moonshot.ai/v1",                # Moonshot Kimi (vision models)
    "together": "https://api.together.xyz/v1",           # Llama 4 / Qwen-VL
    "ollama": "http://localhost:11434/v1",               # local models on your laptop
}


def make_llm(system_prompt: str):
    provider = env("LLM_PROVIDER", "openai").lower()
    model = env("LLM_MODEL")
    key = env("LLM_API_KEY")

    if provider == "openai":
        from pipecat.services.openai.llm import OpenAILLMService
        return OpenAILLMService(api_key=key or env("OPENAI_API_KEY"),
                                settings=OpenAILLMService.Settings(model=model or "gpt-4.1-mini", system_instruction=system_prompt))
    if provider == "anthropic":
        from pipecat.services.anthropic.llm import AnthropicLLMService
        return AnthropicLLMService(api_key=key or env("ANTHROPIC_API_KEY"),
                                   settings=AnthropicLLMService.Settings(model=model or "claude-sonnet-4-5", system_instruction=system_prompt))
    if provider in ("google", "gemini"):
        from pipecat.services.google.llm import GoogleLLMService
        return GoogleLLMService(api_key=key or env("GOOGLE_API_KEY"),
                                settings=GoogleLLMService.Settings(model=model or "gemini-2.5-flash", system_instruction=system_prompt))
    if provider == "groq":
        from pipecat.services.groq.llm import GroqLLMService
        return GroqLLMService(api_key=key or env("GROQ_API_KEY"),
                              settings=GroqLLMService.Settings(model=model or "meta-llama/llama-4-scout-17b-16e-instruct", system_instruction=system_prompt))
    if provider == "openrouter":
        from pipecat.services.openrouter.llm import OpenRouterLLMService
        return OpenRouterLLMService(api_key=key or env("OPENROUTER_API_KEY"),
                                    settings=OpenRouterLLMService.Settings(model=model or "openai/gpt-4.1-mini", system_instruction=system_prompt))
    if provider == "sarvam":
        from pipecat.services.sarvam.llm import SarvamLLMService
        return SarvamLLMService(api_key=key or env("SARVAM_API_KEY"),
                                settings=SarvamLLMService.Settings(model=model or "sarvam-105b-conversations", system_instruction=system_prompt))
    if provider in COMPATIBLE_BASE_URLS or provider == "compatible":
        from pipecat.services.openai.llm import OpenAILLMService
        base_url = env("LLM_BASE_URL", COMPATIBLE_BASE_URLS.get(provider))
        if not base_url:
            # without this the OpenAI client quietly falls back to api.openai.com
            raise ValueError("Set LLM_BASE_URL for LLM_PROVIDER=compatible")
        if not model:
            raise ValueError(f"Set LLM_MODEL for provider '{provider}'")
        return OpenAILLMService(api_key=key or "none", base_url=base_url,
                                settings=OpenAILLMService.Settings(model=model, system_instruction=system_prompt))
    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'")


def make_stt():
    provider = env("STT_PROVIDER", "openai").lower()
    model = env("STT_MODEL")
    lang = _lang(env("LANGUAGE"))

    if provider == "sarvam":
        from pipecat.services.sarvam.stt import SarvamSTTService
        return SarvamSTTService(api_key=env("SARVAM_API_KEY"), model=model or "saaras:v3",
                                settings=SarvamSTTService.Settings(language=lang))
    if provider == "groq":
        from pipecat.services.groq.stt import GroqSTTService
        return GroqSTTService(api_key=env("GROQ_API_KEY"), model=model or "whisper-large-v3-turbo",
                              language=lang)
    if provider == "openai":
        from pipecat.services.openai.stt import OpenAISTTService
        return OpenAISTTService(api_key=env("OPENAI_API_KEY"), model=model or "gpt-4o-mini-transcribe",
                                base_url=env("STT_BASE_URL"), language=lang)
    raise ValueError(f"Unknown STT_PROVIDER '{provider}'")


def make_tts():
    provider = env("TTS_PROVIDER", "openai").lower()
    model = env("TTS_MODEL")
    voice = env("TTS_VOICE")

    if provider == "sarvam":
        from pipecat.services.sarvam.tts import SarvamTTSService
        return SarvamTTSService(api_key=env("SARVAM_API_KEY"), model=model or "bulbul:v3",
                                voice_id=voice or "shubh",
                                settings=SarvamTTSService.Settings(language=_lang(env("LANGUAGE")) or Language("hi-IN")))
    if provider == "openai":
        from pipecat.services.openai.tts import OpenAITTSService
        return OpenAITTSService(api_key=env("OPENAI_API_KEY"), model=model or "gpt-4o-mini-tts",
                                base_url=env("TTS_BASE_URL"), voice=voice or "alloy")
    raise ValueError(f"Unknown TTS_PROVIDER '{provider}'")


def make_gemini_live(system_prompt: str):
    from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
    kwargs = {}
    if env("GEMINI_LIVE_MODEL"):
        kwargs["settings"] = GeminiLiveLLMService.Settings(model=env("GEMINI_LIVE_MODEL"))
    return GeminiLiveLLMService(api_key=env("GOOGLE_API_KEY"), voice_id=env("TTS_VOICE", "Puck"),
                                system_instruction=system_prompt, **kwargs)
