import os
from dotenv import load_dotenv

# Carica il file .env se presente
load_dotenv()

# Gemini Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("ERRORE: La variabile GEMINI_API_KEY non è impostata nel file .env")

# Barge-in Config (Disattivato di default per evitare auto-interruzione)
ENABLE_BARGE_IN = os.getenv("ENABLE_BARGE_IN", "False").lower() in ("true", "1", "yes")

# Audio Config
AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", 16000))
AUDIO_CHANNELS = int(os.getenv("AUDIO_CHANNELS", 1))

# Vosk Config
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "model/vosk-model-small-it-0.22")
