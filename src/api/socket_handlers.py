
from src.services.socket_service import socket_manager
from src.core.tts_engine import engine
from src.core.config import LANG_MAP
import asyncio
import io
import scipy.io.wavfile as wav
import numpy as np
import re

def setup_socket_handlers():
    sio = socket_manager.sio

    # --- 1. FULL SENTIMENT/TRANSLATION SOCKET (/sentiment) ---
    @sio.on('connect', namespace='/sentiment')
    async def connect_sentiment(sid, environ):
        print(f"Client connected to /sentiment: {sid}")
        await sio.emit('status', {'msg': 'Connected to Sentiment TTS'}, to=sid, namespace='/sentiment')

    @sio.on('synthesize', namespace='/sentiment')
    async def handle_sentiment_synthesize(sid, data):
        """
        Full Pipeline: Translate -> Synthesize (Streaming)
        """
        text = data.get('text', '')
        lang_name = data.get('language', 'english')
        
        print(f"[Sentiment] Request: {text[:20]}... ({lang_name})")
        
        if not text:
            await sio.emit('error', {'msg': 'No text provided'}, to=sid, namespace='/sentiment')
            return

        lang_code = LANG_MAP.get(lang_name.lower(), 'eng')
        
        loop = asyncio.get_event_loop()

        try:
            # Step 1: Translate (Blocking/Sync)
            # Run in executor
            translated_text = await loop.run_in_executor(None, engine.translate_if_needed, text, lang_code)
            
            if translated_text != text:
                print(f"[Sentiment] Translated to: {translated_text[:20]}...")
                # Notify client of translation
                await sio.emit('translation', {'original': text, 'translated': translated_text}, to=sid, namespace='/sentiment')
            
            # Step 2: Synthesize (Streaming similar to Multilingual but on translated text)
            # We reuse the chunking logic for better UX
            await stream_synthesis(sid, translated_text, lang_name, namespace='/sentiment')
            
        except Exception as e:
            print(f"[Sentiment] Error: {e}")
            await sio.emit('error', {'msg': str(e)}, to=sid, namespace='/sentiment')


    # --- 2. SIMPLE MULTILINGUAL SOCKET (/multilingual) ---
    @sio.on('connect', namespace='/multilingual')
    async def connect_multilingual(sid, environ):
        print(f"Client connected to /multilingual: {sid}")
        await sio.emit('status', {'msg': 'Connected to Multilingual TTS'}, to=sid, namespace='/multilingual')

    @sio.on('synthesize', namespace='/multilingual')
    async def handle_multilingual_synthesize(sid, data):
        """
        Simple Pipeline: No Translate -> Smart Chunking -> Streaming
        """
        text = data.get('text', '')
        lang_name = data.get('language', 'english')
        
        print(f"[Multilingual] Request: {text[:20]}... ({lang_name})")
        
        if not text:
            await sio.emit('error', {'msg': 'No text provided'}, to=sid, namespace='/multilingual')
            return

        # Direct streaming
        await stream_synthesis(sid, text, lang_name, namespace='/multilingual')


    # --- SHARED STREAMING LOGIC ---
    async def stream_synthesis(sid, text, lang_name, namespace):
        # Smart Chunking
        tokens = re.split(r'([.,!?;]+)', text)
        chunks = []
        current_chunk = ""
        word_count = 0
        SOFT_LIMIT = 5
        HARD_LIMIT = 10
        
        for token in tokens:
            if not token.strip():
                continue
            current_chunk += token
            word_count += len(token.split())
            
            is_end_sentence = any(p in token for p in ".!?")
            is_comma = "," in token
            
            should_send = False
            if is_end_sentence: should_send = True
            elif word_count >= SOFT_LIMIT and is_comma: should_send = True
            elif word_count >= HARD_LIMIT: should_send = True
                
            if should_send:
                final_chunk = current_chunk.strip()
                # Fix: If chunk is just punctuation, append to previous if possible
                if final_chunk and not any(c.isalnum() for c in final_chunk) and chunks:
                    chunks[-1] += final_chunk
                else:
                    chunks.append(final_chunk)
                    
                current_chunk = ""
                word_count = 0
                
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
            
        await sio.emit('stream_start', {'total_chunks': len(chunks)}, to=sid, namespace=namespace)
        
        loop = asyncio.get_event_loop()
        
        async def process_chunk(chunk_text, index):
            try:
                # Synthesize
                # Speed 1.1 = Slower = Clearer
                waveform, sr = await loop.run_in_executor(None, engine.synthesize, chunk_text, lang_name, 1.1)
                
                # Convert to bytes
                waveform = waveform / np.max(np.abs(waveform)) * 32767
                waveform = waveform.astype(np.int16)
                byte_io = io.BytesIO()
                wav.write(byte_io, sr, waveform)
                wav_bytes = byte_io.getvalue()
                
                await sio.emit('audio_chunk', {
                    'chunk_index': index,
                    'audio': wav_bytes, 
                    'text_chunk': chunk_text
                }, to=sid, namespace=namespace)
                
            except Exception as e:
                print(f"Error chunk {index}: {e}")
                await sio.emit('error', {'msg': str(e)}, to=sid, namespace=namespace)

        for i, chunk in enumerate(chunks):
            await process_chunk(chunk, i)
            
        await sio.emit('stream_complete', {}, to=sid, namespace=namespace)
