from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel
import numpy as np
import io
import scipy.io.wavfile as wav
import asyncio
from concurrent.futures import ThreadPoolExecutor

from src.core.tts_engine import engine
from src.core.config import LANG_MAP
from src.services.socket_service import socket_manager

router = APIRouter()

class TTSRequest(BaseModel):
    text: str
    language: str

@router.get("/health")
def health_check():
    return {"status": "ok"}

@router.get("/languages")
def get_languages():
    # Return user-friendly language names (keys with length > 3)
    languages = sorted([k for k in LANG_MAP.keys() if len(k) > 3])
    # Capitalize for display
    languages = [l.capitalize() for l in languages]
    return {"languages": languages}

@router.post("/synthesize")
async def synthesize(req: TTSRequest):
    try:
        lang_name = req.language.lower()
        print(f"Received request: {req.text} in {lang_name}")
        
        # Notify clients via socket
        await socket_manager.emit_status("processing_started", {"text": req.text[:20] + "...", "lang": lang_name})
        
        # Resolve code
        lang_code = LANG_MAP.get(lang_name, 'eng')
        
        # Translation Step (Run in executor to avoid blocking if heavy, though it's network bound usually)
        # But MMSEngine.translate_if_needed uses GoogleTranslator which is blocking or uses requests.
        loop = asyncio.get_event_loop()
        
        # We'll run the whole synthesis pipeline in executor to be safe and keep event loop free
        def run_synthesis_task():
            # 1. Translate
            text_to_process = engine.translate_if_needed(req.text, lang_code)
            
            # 2. Synthesize
            # Check if we should emit an update? We can't easily validly from thread to async socket without loop ref.
            # We'll just return the result.
            return engine.synthesize(text_to_process, lang=lang_name)

        # Emit "synthesizing" state
        await socket_manager.emit_progress("Synthesizing audio...", 50)
        
        # Run blocking task
        waveform, sr = await loop.run_in_executor(None, run_synthesis_task)
        
        await socket_manager.emit_progress("Conversion complete", 90)
        
        # Normalize and convert to 16-bit PCM
        waveform = waveform / np.max(np.abs(waveform)) * 32767
        waveform = waveform.astype(np.int16)
        
        # Write to in-memory bytes
        byte_io = io.BytesIO()
        wav.write(byte_io, sr, waveform)
        byte_io.seek(0)
        
        await socket_manager.emit_status("completed", {"size": len(waveform)})
        
        return Response(content=byte_io.read(), media_type="audio/wav")
    except Exception as e:
        print(f"Error: {e}")
        await socket_manager.emit_status("error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
