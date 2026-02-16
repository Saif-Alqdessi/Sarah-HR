import os
from groq import Groq
from typing import BinaryIO

class GroqTranscriber:
    """
    Dedicated Arabic transcription using Groq Whisper-large-v3-turbo
    FREE tier, no rate limits, optimized for Arabic dialects
    """
    
    def __init__(self):
        try:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                print("⚠️ Warning: GROQ_API_KEY not found in environment variables")
                self.client = None
            else:
                self.client = Groq(api_key=api_key)
            self.model = "whisper-large-v3-turbo"
        except Exception as e:
            print(f"⚠️ Warning: Failed to initialize Groq client: {str(e)}")
            self.client = None
    
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
        
        if self.client is None:
            print("❌ Cannot transcribe: Groq client not initialized")
            return "عذراً، حدث خطأ في نظام التعرف على الصوت"
        
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
            return "عذراً، حدث خطأ في نظام التعرف على الصوت"
    
    def transcribe_audio_with_timestamps(
        self,
        audio_file: BinaryIO,
        language: str = "ar"
    ) -> dict:
        """
        Get transcription with word-level timestamps
        """
        
        if self.client is None:
            print("❌ Cannot transcribe with timestamps: Groq client not initialized")
            return {"text": "عذراً، حدث خطأ في نظام التعرف على الصوت", "words": []}
        
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
            return {"text": "عذراً، حدث خطأ في نظام التعرف على الصوت", "words": []}
