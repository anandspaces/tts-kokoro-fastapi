import threading
import torch
import numpy as np
import scipy.io.wavfile as wav
import re
import io
from transformers import VitsModel, AutoTokenizer
from deep_translator import GoogleTranslator
from src.core.config import settings, LANG_MAP
from collections import OrderedDict

def normalize_math_english(text):
    """
    English-specific math normalization.
    """
    # Superscripts
    text = re.sub(r'(\w+)\^2', r'\1 squared', text)
    text = re.sub(r'(\w+)\^3', r'\1 cubed', text)
    
    # Operators
    text = text.replace('+', ' plus ')
    text = text.replace('=', ' equals ')
    text = text.replace('*', ' times ')
    text = text.replace('/', ' divided by ')
    
    # Common symbols
    text = text.replace('∫', 'integral ')
    text = text.replace('π', 'pie')
    
    return text

class MMSEngine:
    def __init__(self):
        self.loaded_models = OrderedDict() # Cache: {lang_code: (model, tokenizer)}
        self.device = settings.MODEL_DEVICE
        self.max_models = settings.MAX_LOADED_MODELS
        self.lock = threading.Lock()

    def load_lang(self, lang_code):
        with self.lock:
            # 1. Check if already loaded
            if lang_code in self.loaded_models:
                # Move to end (most recently used)
                self.loaded_models.move_to_end(lang_code)
                return

            print(f"Loading model for language: {lang_code}...")
            model_id = f"facebook/mms-tts-{lang_code}"
            
            try:
                tokenizer = AutoTokenizer.from_pretrained(model_id)
                model = VitsModel.from_pretrained(model_id)
                model.to(self.device)
                
                # 2. Check if cache is full
                if len(self.loaded_models) >= self.max_models:
                    # Remove first item (least recently used)
                    removed_lang, _ = self.loaded_models.popitem(last=False)
                    print(f"Cache full. Unloaded model: {removed_lang}")
                
                # 3. Add to cache
                self.loaded_models[lang_code] = (model, tokenizer)
                print(f"Successfully loaded {model_id}. Cached models: {list(self.loaded_models.keys())}")
                
            except Exception as e:
                print(f"Error loading model {model_id}: {e}")
                raise

    @property
    def model(self):
        """Helper to get current model (last used)"""
        if not self.loaded_models:
            return None
        return list(self.loaded_models.values())[-1][0]

    @property
    def tokenizer(self):
        """Helper to get current tokenizer (last used)"""
        if not self.loaded_models:
            return None
        return list(self.loaded_models.values())[-1][1]

    def translate_if_needed(self, text: str, lang_code: str) -> str:
        """
        Translates text to the target language if it's not English.
        Uses Google Translator.
        """
        if lang_code == 'eng':
            return text

        # Map MMS code to Google Translate code
        gt_lang = lang_code
        if lang_code == "san": gt_lang = "sa"
        if lang_code == "hin": gt_lang = "hi"
        if lang_code == "fra": gt_lang = "fr"
        if lang_code == "tel": gt_lang = "te"
        if lang_code == "tam": gt_lang = "ta"
        if lang_code == "mal": gt_lang = "ml"
        if lang_code == "kan": gt_lang = "kn"
        if lang_code == "pan": gt_lang = "pa"
        if lang_code == "guj": gt_lang = "gu"
        if lang_code == "asm": gt_lang = "as"
        
        try:
            print(f"Translating to {gt_lang}...")
            translated = GoogleTranslator(source='auto', target=gt_lang).translate(text)
            print(f"Translated: {translated}")
            return translated
        except Exception as te:
            print(f"Translation failed: {te}. Using original text.")
            return text

    def synthesize(self, text: str, lang: str="eng", speed: float=1.0):
        # 1. Resolve Language
        lang_code = LANG_MAP.get(lang.lower(), "eng")
        
        # 2. Normalize (English only for now)
        if lang_code == "eng":
            text = normalize_math_english(text)
            
        print(f"Synthesizing '{text}' in {lang_code}...")
        
        # 3. Load Model
        self.load_lang(lang_code)
        
        # 4. Infer
        inputs = self.tokenizer(text, return_tensors="pt")
        inputs = inputs.to(self.device)

        # MMS/VITS Parameters:
        # noise_scale: How random/expressive (0.667 default). 
        # length_scale: Speed inverse. 1.0=Normal, 1.1=Slower(Clearer), 0.9=Faster.
        
        with torch.no_grad():
            output = self.model(
                input_ids=inputs.input_ids, 
                attention_mask=inputs.attention_mask,
            ).waveform
        
        # Convert to numpy
        waveform = output.cpu().numpy().squeeze()
        
        return waveform, self.model.config.sampling_rate

# Shared Singleton
engine = MMSEngine()
