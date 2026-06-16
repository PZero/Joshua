import os
import json
from vosk import Model, KaldiRecognizer
from src.config import VOSK_MODEL_PATH, AUDIO_SAMPLE_RATE

class VoskSTT:
    def __init__(self, model_path=VOSK_MODEL_PATH, sample_rate=AUDIO_SAMPLE_RATE):
        self.model_path = model_path
        self.sample_rate = sample_rate
        self.model = None

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"ERRORE: Modello Vosk non trovato al percorso: {self.model_path}\n"
                f"Assicurati di scaricarlo ed estrarlo in quella cartella prima di avviare l'assistente."
            )

        print(f"[Joshua] Caricamento modello STT locale da: {self.model_path}...", flush=True)
        self.model = Model(self.model_path)
        print("[Joshua] Modello Vosk caricato con successo.", flush=True)

    def transcribe(self, audio_bytes):
        """Riceve byte PCM mono 16-bit a 16kHz e restituisce il testo trascritto."""
        if not audio_bytes:
            return ""

        # Crea un riconoscitore Kaldi per questo blocco audio
        recognizer = KaldiRecognizer(self.model, self.sample_rate)
        
        # Elabora l'intera traccia audio ricevuta
        recognizer.AcceptWaveform(audio_bytes)
        
        # Estrae il risultato finale in formato JSON
        result_json = json.loads(recognizer.FinalResult())
        text = result_json.get("text", "")
        
        if text:
            print(f"[STT] Trascrizione: \"{text}\"", flush=True)
        return text
