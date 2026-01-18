import socketio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.api.routes import router as api_router
from src.services.socket_service import socket_manager
import os

from src.api.socket_handlers import setup_socket_handlers

# Initialize FastAPI
fast_app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)

# Register Socket Handlers
setup_socket_handlers()

@fast_app.on_event("startup")
async def startup_event():
    print(f"Pre-loading languages: {settings.PRELOAD_LANGS}...")
    from src.core.tts_engine import engine
    for lang in settings.PRELOAD_LANGS:
        try:
            engine.load_lang(lang)
        except Exception as e:
            print(f"Failed to preload {lang}: {e}")
    print("Pre-loading complete.")

# CORS config
fast_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routes
fast_app.include_router(api_router)

# Mount Static Files
# Check if static directory exists relative to execution path (usually root)
static_dir = os.path.join(os.getcwd(), "static")
if os.path.exists(static_dir):
    # Mount root to static for UI (index.html)
    fast_app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    print(f"Warning: Static directory {static_dir} not found.")

# Wrap with Socket.IO
# socket_path defaults to 'socket.io'
app = socketio.ASGIApp(socket_manager.sio, fast_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
