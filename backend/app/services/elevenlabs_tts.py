"""
ElevenLabs TTS Service
Optimized for Arabic voice synthesis with natural Jordanian dialect.
60-second timeout + tenacity retry (3 attempts, exponential back-off).
"""

import os
import base64
import logging
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# Retry on transient network/server errors only
_RETRY_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)


class ElevenLabsTTS:
    """
    Text-to-Speech service using ElevenLabs API.
    Optimized for Arabic voices with 60s timeout and automatic retries.
    """

    # Default Arabic female voice ID (Aria)
    DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"

    # Shared httpx timeout: 10s connect, 60s read (audio stream can be slow)
    _TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0)

    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY not found in environment variables")

        self.api_url = "https://api.elevenlabs.io/v1"

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> str:
        """
        Synthesize text to speech with 60s timeout and up to 3 retries.

        Args:
            text:     Text to synthesize (Arabic/Jordanian dialect).
            voice_id: ElevenLabs voice ID (defaults to Aria Arabic voice).

        Returns:
            Base64-encoded MP3 audio string, or "" on failure.
        """
        if not self.api_key:
            logger.error("Cannot synthesize: ELEVENLABS_API_KEY is not set")
            return ""

        voice_id = voice_id or self.DEFAULT_VOICE_ID

        try:
            audio_bytes = await self._call_api_with_retry(text, voice_id)
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            logger.info("Audio synthesis OK (%d bytes) for: %s", len(audio_bytes), text[:50])
            return audio_b64

        except Exception as e:
            logger.error("ElevenLabs synthesis failed after retries: %s", e)
            return ""

    @retry(
        retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _call_api_with_retry(self, text: str, voice_id: str) -> bytes:
        """
        Inner async call — retried up to 3 times on timeout / connection errors.
        Non-retried errors (4xx auth, bad request) bubble up immediately.
        """
        url = f"{self.api_url}/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        }

        async with httpx.AsyncClient(timeout=self._TIMEOUT) as client:
            logger.info("Calling ElevenLabs TTS (attempt)...")
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                return response.content

            # 4xx → don't retry (bad key, quota, etc.)
            logger.error(
                "ElevenLabs API error %d: %s",
                response.status_code,
                response.text[:200],
            )
            # Raise a non-retried exception so tenacity gives up immediately
            raise ValueError(f"ElevenLabs HTTP {response.status_code}: {response.text[:120]}")

    def get_available_voices(self) -> list:
        """Return available voices (sync helper, for tooling/debugging only)."""
        if not self.api_key:
            logger.error("Cannot get voices: ELEVENLABS_API_KEY is not set")
            return []

        try:
            import httpx as _httpx
            with _httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    f"{self.api_url}/voices",
                    headers={"xi-api-key": self.api_key},
                )
            if resp.status_code == 200:
                return resp.json().get("voices", [])
            logger.error("ElevenLabs voices error %d: %s", resp.status_code, resp.text[:200])
            return []
        except Exception as e:
            logger.error("Error getting voices: %s", e)
            return []
