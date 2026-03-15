from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    debug: bool = False

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_role_key: str = ""

    # Vapi AI
    vapi_api_key: str = ""
    vapi_assistant_id: str = ""
    vapi_webhook_secret: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"

    # Groq
    groq_api_key: str = ""

    # Multi-provider LLM manager (Phase 1)
    primary_llm_provider: str = "groq"
    fallback_llm_provider: str = "openai"
    max_llm_failures: int = 3
    circuit_breaker_timeout: int = 300

    # Webhook URL
    webhook_url: str = ""

    # Gemini API (scoring & analysis)
    gemini_api_key: str = ""

    # Deepgram (optional backup STT)
    deepgram_api_key: str = ""

    # ElevenLabs TTS
    elevenlabs_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"   # silently ignore unknown .env keys


settings = Settings()
