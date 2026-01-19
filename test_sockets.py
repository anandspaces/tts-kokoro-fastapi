import socketio
import sys
import time
import os
import io
import wave

# Create output directory
os.makedirs('output', exist_ok=True)

# Create a Socket.IO client
sio = socketio.Client()

# Store audio data
audio_buffers = {
    '/sentiment': [],
    '/multilingual': []
}
completed_tasks = {
    '/sentiment': False,
    '/multilingual': False
}

def check_completion():
    if completed_tasks['/sentiment'] and completed_tasks['/multilingual']:
        print("\n✅ All tasks completed.")
        
        # Save buffers to files
        for namespace, chunks in audio_buffers.items():
            filename = f"output/{namespace.strip('/')}.wav"
            if not chunks:
                print(f"No audio received for {namespace}")
                continue
                
            try:
                # Read first chunk to get parameters
                first_chunk = io.BytesIO(chunks[0])
                with wave.open(first_chunk, 'rb') as w:
                    params = w.getparams()
                    frames = w.readframes(w.getnframes())
                
                # Read subsequent chunks
                for chunk in chunks[1:]:
                    with wave.open(io.BytesIO(chunk), 'rb') as w:
                        frames += w.readframes(w.getnframes())
                        
                # Write combined file
                with wave.open(filename, 'wb') as w:
                    w.setparams(params)
                    w.writeframes(frames)
                    
                print(f"Saved audio to {filename}")
            except Exception as e:
                print(f"Error saving {filename}: {e}")

        print("Disconnecting...")
        sio.disconnect()
        time.sleep(1)
        sys.exit(0)

# --- SENTIMENT HANDLERS ---
@sio.on('connect', namespace='/sentiment')
def on_connect_sentiment():
    print("[/sentiment] Connected")

@sio.on('status', namespace='/sentiment')
def on_status_sentiment(data):
    print(f"[/sentiment] Status: {data}")

@sio.on('translation', namespace='/sentiment')
def on_translation_sentiment(data):
    print(f"[/sentiment] Translation: {data}")

@sio.on('stream_start', namespace='/sentiment')
def on_stream_start_sentiment(data):
    print(f"[/sentiment] Stream start")

@sio.on('audio_chunk', namespace='/sentiment')
def on_audio_chunk_sentiment(data):
    print(f"[/sentiment] Received audio chunk {data.get('chunk_index')}")
    audio = data.get('audio')
    if audio:
        audio_buffers['/sentiment'].append(audio)

@sio.on('stream_complete', namespace='/sentiment')
def on_stream_complete_sentiment(data):
    print(f"[/sentiment] Stream complete")
    completed_tasks['/sentiment'] = True
    check_completion()

@sio.on('error', namespace='/sentiment')
def on_error_sentiment(data):
    print(f"[/sentiment] ❌ Error: {data}")
    completed_tasks['/sentiment'] = True 
    check_completion()

# --- MULTILINGUAL HANDLERS ---
@sio.on('connect', namespace='/multilingual')
def on_connect_multilingual():
    print("[/multilingual] Connected")

@sio.on('status', namespace='/multilingual')
def on_status_multilingual(data):
    print(f"[/multilingual] Status: {data}")

@sio.on('stream_start', namespace='/multilingual')
def on_stream_start_multilingual(data):
    print(f"[/multilingual] Stream start")

@sio.on('audio_chunk', namespace='/multilingual')
def on_audio_chunk_multilingual(data):
    print(f"[/multilingual] Received audio chunk {data.get('chunk_index')}")
    audio = data.get('audio')
    if audio:
        audio_buffers['/multilingual'].append(audio)

@sio.on('stream_complete', namespace='/multilingual')
def on_stream_complete_multilingual(data):
    print(f"[/multilingual] Stream complete")
    completed_tasks['/multilingual'] = True
    check_completion()

@sio.on('error', namespace='/multilingual')
def on_error_multilingual(data):
    print(f"[/multilingual] ❌ Error: {data}")
    completed_tasks['/multilingual'] = True 
    check_completion()

@sio.on('disconnect')
def on_disconnect():
    pass

def main():
    # Get Inputs
    print("\n--- Socket TTS Tester ---")
    
    print("\n[Sentiment Socket]")
    sent_text = input("Enter text: ")
    sent_lang = input("Enter language (e.g., english, hindi, french): ")
    
    print("\n[Multilingual Socket]")
    multi_text = input("Enter text: ")
    multi_lang = input("Enter language (e.g., english, hindi, french): ")
    
    # Defaults
    if not sent_text: sent_text = "This is a default sentiment test."
    if not sent_lang: sent_lang = "english"
    
    if not multi_text: multi_text = "This is a default multilingual test."
    if not multi_lang: multi_lang = "english"

    try:
        url = 'http://localhost:8000'
        print(f"\nConnecting to {url}...")
        # Connect to both namespaces
        sio.connect(url, namespaces=['/sentiment', '/multilingual'])
        
        # Emit events after connection
        print("Sending requests...")
        sio.emit('synthesize', {'text': sent_text, 'language': sent_lang}, namespace='/sentiment')
        sio.emit('synthesize', {'text': multi_text, 'language': multi_lang}, namespace='/multilingual')
        
        sio.wait()
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Make sure the server is running (python -m src.main)")

if __name__ == '__main__':
    main()
