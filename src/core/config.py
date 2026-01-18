import os
from pydantic_settings import BaseSettings
from typing import Dict

class Settings(BaseSettings):
    APP_NAME: str = "Kokoro/MMS TTS API"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # Model Settings (could be loaded from env)
    MODEL_DEVICE: str = "cpu"
    MAX_LOADED_MODELS: int = 3
    PRELOAD_LANGS: list = []
    
    class Config:
        env_file = ".env"

settings = Settings()

# Map user friendly language names to ISO 639-3 codes used by MMS
LANG_MAP: Dict[str, str] = {
    "english": "eng",
    "eng": "eng",
    "french": "fra",
    "fra": "fra",
    "hindi": "hin",
    "hin": "hin",
    "sanskrit": "san",
    "san": "san",
    "telugu": "tel",
    "tel": "tel",
    "tamil": "tam",
    "tam": "tam",
    "malayalam": "mal",
    "mal": "mal",
    "kannada": "kan",
    "kan": "kan",
    "punjabi": "pan",
    "pan": "pan",
    "gujarati": "guj",
    "guj": "guj",
    "assamese": "asm",
    "asm": "asm",
    "hinglish": "hin", # Approximated via Hindi
}
