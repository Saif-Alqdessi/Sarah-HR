import requests
import os
from dotenv import load_dotenv

load_dotenv()

VAPI_API_KEY = os.getenv("VAPI_API_KEY")
ASSISTANT_ID = "fb90c82d-00fa-4c8f-ab0c-69befb69e0bd"
VAPI_API_URL = f"https://api.vapi.ai/assistant/{ASSISTANT_ID}"

def update_vapi_assistant():
    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json",
    }

    # تأكد أن ngrok شغال والرابط صحيح في .env
    webhook_url = os.getenv("WEBHOOK_URL", "").rstrip("/")
    server_url = f"{webhook_url}/api/agent-response"

    payload = {
    "name": "Sarah - Final Stable",
    "transcriber": {
        "provider": "openai",
        "model": "gpt-4o-mini-transcribe", # الموديل الوحيد المستقر حالياً
        "language": "ar"
    },
    "model": {
        "provider": "groq", 
        "model": "llama-3.1-8b-instant" 
    },
    "voice": {
        "provider": "11labs",
        "voiceId": "pNInz6obpgDQGcFmaJgB", # صوت آدم
        "model": "eleven_multilingual_v2"
    },
    "serverUrl": os.getenv("WEBHOOK_URL") 
}

    response = requests.patch(VAPI_API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        print("✅ سارة الآن ذكية جداً وجاهزة للمقابلة!")
    else:
        print(f"❌ خطأ: {response.text}")

if __name__ == "__main__":
    update_vapi_assistant()