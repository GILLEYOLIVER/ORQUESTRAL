from app.core.config import Settings
from app.modules.agents.providers.base import LanguageModelProvider, LanguageModelProviderError
from app.modules.agents.providers.local import LocalLanguageModelProvider
from app.modules.agents.providers.openai_compatible import OpenAICompatibleLanguageModelProvider


def create_language_model_provider(provider: str, settings: Settings) -> LanguageModelProvider:
    if provider == "local":
        return LocalLanguageModelProvider()
    if provider == "openai_compatible":
        api_key = (settings.ai_provider_api_key or "").strip()
        if not api_key:
            raise LanguageModelProviderError("O provedor externo deste agente ainda não possui credencial configurada.")
        return OpenAICompatibleLanguageModelProvider(base_url=str(settings.ai_provider_base_url), api_key=api_key, timeout_seconds=settings.ai_provider_timeout_seconds, input_cost_per_million_microunits=settings.ai_input_cost_per_million_tokens_microusd, output_cost_per_million_microunits=settings.ai_output_cost_per_million_tokens_microusd)
    raise LanguageModelProviderError("Provedor de linguagem não suportado.")
