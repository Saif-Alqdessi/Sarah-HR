"""
Groq Whisper transcriber — BULLETPROOF.
Every return path casts to str(). No .strip() on unknown types.
"""

import os
import base64
import io
import logging
from groq import Groq
from typing import BinaryIO, Union

logger = logging.getLogger(__name__)

# Whisper prompt hint: common Jordanian Arabic words + interview vocabulary.
_WHISPER_ARABIC_PROMPT = (
    "مقابلة عمل، توظيف، خبرة، راتب، مهارة، عمان، الأردن، دينار، سنة، سنوات، "
    "شغل، بدي، عملت، اشتغلت، كيفك، شو، ليش، منيح، هيك، بكتدير، "
    "راتبتي المتوقع، مجال العمل، خبرة عملية، سنوات خبرة، "
    # List of expected terms (names, technical words, company jargon)
    "React, Python, FastAPI, برمجة، مبرمج، شركة قبلان"
)

# Error fallback — returned when transcription fails entirely
_FALLBACK = ""


class GroqTranscriber:
    """
    Dedicated Arabic transcription using Groq Whisper-large-v3-turbo.
    Every method guarantees a str return — no more 'int has no .strip()'.
    """

    def __init__(self):
        try:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                logger.warning("GROQ_API_KEY not found in environment variables")
                self.client = None
            else:
                self.client = Groq(api_key=api_key)
            self.model = "whisper-large-v3-turbo"
        except Exception as e:
            logger.warning("Failed to initialize Groq client: %s", e)
            self.client = None

    @staticmethod
    def _safe_str(value) -> str:
        """Force ANY value to a clean string. The universal fix."""
        try:
            if value is None:
                return ""
            result = str(value).strip()
            return result
        except Exception:
            return ""

    def transcribe_audio(self, audio_file: BinaryIO, language: str = "ar") -> str:
        """Transcribe audio to Arabic text. ALWAYS returns str."""
        if self.client is None:
            logger.error("Cannot transcribe: Groq client not initialized")
            return _FALLBACK

        try:
            transcription = self.client.audio.transcriptions.create(
                file=audio_file,
                model=self.model,
                language=language,
                temperature=0.0,
                response_format="text",
                prompt=_WHISPER_ARABIC_PROMPT,
            )

            result = self._safe_str(transcription)
            logger.info("Transcription: %s", result[:80])
            return result

        except Exception as e:
            logger.error("Groq transcription error: %s", e)
            return _FALLBACK

    def transcribe_audio_with_timestamps(
        self,
        audio_file: BinaryIO,
        language: str = "ar",
    ) -> dict:
        """Get transcription with word-level timestamps."""
        if self.client is None:
            return {"text": _FALLBACK, "words": []}

        try:
            transcription = self.client.audio.transcriptions.create(
                file=audio_file,
                model=self.model,
                language=language,
                temperature=0.0,
                response_format="verbose_json",
                timestamp_granularities=["word"],
            )
            return transcription.model_dump()
        except Exception as e:
            logger.error("Groq timestamped transcription error: %s", e)
            return {"text": _FALLBACK, "words": []}

    async def transcribe(self, audio_data: Union[str, bytes], language: str = "ar") -> str:
        """
        Async-compatible entry point used by the WebSocket handler.
        Accepts base64 string OR raw bytes. ALWAYS returns str.
        """
        if self.client is None:
            return _FALLBACK

        try:
            # Decode base64 if a string was passed
            if isinstance(audio_data, str):
                raw_bytes = base64.b64decode(audio_data)
            else:
                raw_bytes = audio_data

            audio_buffer = io.BytesIO(raw_bytes)
            audio_buffer.name = "audio.webm"

            return self.transcribe_audio(audio_buffer, language=language)

        except Exception as e:
            logger.error("Error in async transcribe(): %s", e)
            return _FALLBACK
