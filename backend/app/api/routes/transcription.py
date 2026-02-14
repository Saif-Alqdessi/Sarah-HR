from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.services.groq_transcriber import GroqTranscriber

router = APIRouter()
transcriber = GroqTranscriber()

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...)
):
    """
    Transcribe audio file to Arabic text using Groq Whisper
    
    Accepts: webm, mp3, wav, m4a
    Returns: {"text": "النص المترجم"}
    """
    
    # Validate file type
    allowed_types = ["audio/webm", "audio/mpeg", "audio/wav", "audio/mp4", "audio/x-m4a"]
    if audio.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {allowed_types}"
        )
    
    try:
        # Read audio file
        audio_bytes = await audio.read()
        
        # Save temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_file:
            temp_file.write(audio_bytes)
            temp_file.flush()
            
            # Transcribe
            with open(temp_file.name, "rb") as f:
                transcribed_text = transcriber.transcribe_audio(f, language="ar")
        
        # Clean up
        import os
        os.unlink(temp_file.name)
        
        if not transcribed_text:
            raise HTTPException(status_code=500, detail="Transcription failed")
        
        return JSONResponse({
            "success": True,
            "text": transcribed_text,
            "language": "ar"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transcribe-verbose")
async def transcribe_audio_verbose(
    audio: UploadFile = File(...)
):
    """
    Get transcription with word-level timestamps
    """
    
    try:
        audio_bytes = await audio.read()
        
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_file:
            temp_file.write(audio_bytes)
            temp_file.flush()
            
            with open(temp_file.name, "rb") as f:
                result = transcriber.transcribe_audio_with_timestamps(f, language="ar")
        
        import os
        os.unlink(temp_file.name)
        
        return JSONResponse({
            "success": True,
            "transcription": result
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
