"""
ElevenLabs TTS Service
Optimized for Arabic voice synthesis with natural Jordanian dialect
"""

import os
import base64
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ElevenLabsTTS:
    """
    Text-to-Speech service using ElevenLabs API
    Optimized for Arabic voices
    """
    
    # Default Arabic female voice ID (Aria)
    DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
    
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY not found in environment variables")
        
        self.api_url = "https://api.elevenlabs.io/v1"
    
    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None
    ) -> str:
        """
        Synthesize text to speech
        
        Args:
            text: Text to synthesize (in Arabic)
            voice_id: Voice ID to use (defaults to Arabic female voice)
            
        Returns:
            Base64-encoded audio data
        """
        if not self.api_key:
            logger.error("Cannot synthesize: ElevenLabs API key not set")
            return ""
        
        # Use default Arabic voice if not specified
        voice_id = voice_id or self.DEFAULT_VOICE_ID
        
        try:
            # API request to ElevenLabs
            url = f"{self.api_url}/text-to-speech/{voice_id}"
            
            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json"
            }
            
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            }
            
            logger.info(f"🔊 Synthesizing: {text[:50]}...")
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                # Convert binary audio to base64 for WebSocket transmission
                audio_data = base64.b64encode(response.content).decode('utf-8')
                logger.info("✅ Audio synthesis successful")
                return audio_data
            else:
                logger.error(f"❌ ElevenLabs API error: {response.status_code} - {response.text}")
                return ""
                
        except Exception as e:
            logger.error(f"❌ ElevenLabs synthesis error: {str(e)}")
            return ""
    
    def get_available_voices(self) -> list:
        """
        Get list of available voices
        
        Returns:
            List of voice objects with ID, name, etc.
        """
        if not self.api_key:
            logger.error("Cannot get voices: ElevenLabs API key not set")
            return []
        
        try:
            url = f"{self.api_url}/voices"
            headers = {"xi-api-key": self.api_key}
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                voices = response.json().get("voices", [])
                return voices
            else:
                logger.error(f"❌ ElevenLabs API error: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error getting voices: {str(e)}")
            return []
