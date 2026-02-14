from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    debug: bool = False
    
    # Supabase (env: SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY)
    # Use SERVICE_ROLE_KEY for backend to bypass RLS; anon key may block inserts.
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_role_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1" # القيمة الافتراضية
    # Vapi AI
    vapi_api_key: str = ""
    vapi_assistant_id: str = ""
    vapi_webhook_secret: str = ""
    
    # OpenAI (Intelligent Agent - gpt-4o-mini)
    openai_api_key: str = ""
    groq_api_key: str = ""
    # Webhook URL (ngrok HTTPS base - e.g. https://abc123.ngrok-free.app)
    webhook_url: str = ""
    
    # Gemini API (scoring & analysis)
    gemini_api_key: str = ""
    
    # Deepgram (optional backup STT)
    deepgram_api_key: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        


settings = Settings()
