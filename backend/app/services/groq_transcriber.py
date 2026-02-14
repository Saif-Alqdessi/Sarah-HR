import os
from groq import Groq
from typing import BinaryIO

class GroqTranscriber:
    """
    Dedicated Arabic transcription using Groq Whisper-large-v3-turbo
    FREE tier, no rate limits, optimized for Arabic dialects
    """
    
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "whisper-large-v3-turbo"
    
    def transcribe_audio(
        self,
        audio_file: BinaryIO,
        language: str = "ar"
    ) -> str:
        """
        Transcribe audio to Arabic text
        
        Args:
            audio_file: Audio file (webm, mp3, wav)
            language: Language code (ar for Arabic)
            
        Returns:
            Transcribed text in Arabic
        """
        
        try:
            transcription = self.client.audio.transcriptions.create(
                file=audio_file,
                model=self.model,
                language=language,  # Force Arabic
                temperature=0.0,  # Deterministic
                response_format="text"
            )
            
            # Groq returns plain text
            transcribed_text = transcription.strip()
            
            print(f"✅ Transcription: {transcribed_text}")
            
            return transcribed_text
            
        except Exception as e:
            print(f"❌ Groq transcription error: {str(e)}")
            return ""
    
    def transcribe_audio_with_timestamps(
        self,
        audio_file: BinaryIO,
        language: str = "ar"
    ) -> dict:
        """
        Get transcription with word-level timestamps
        """
        
        try:
            transcription = self.client.audio.transcriptions.create(
                file=audio_file,
                model=self.model,
                language=language,
                temperature=0.0,
                response_format="verbose_json",
                timestamp_granularities=["word"]
            )
            
            return transcription.model_dump()
            
        except Exception as e:
            print(f"❌ Groq transcription error: {str(e)}")
            return {"text": "", "words": []}
