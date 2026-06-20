import os
import sys
import time
import subprocess
import wave

# Esegui la configurazione ALSA dinamica prima di caricare sounddevice
from src.main import setup_audio_config
setup_audio_config()

import sounddevice as sd
import numpy as np

def save_wav(filename, data_bytes, sample_rate):
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2) # 16-bit PCM = 2 byte
        wf.setframerate(sample_rate)
        wf.writeframes(data_bytes)

def main():
    print("==================================================", flush=True)
    # Titolo stile anni '80
    print("         JOSHUA - SIMPLE AUDIO TEST MODULE        ", flush=True)
    print("==================================================", flush=True)
    
    # 1. Test di Riproduzione
    print("\n1. Test di RIPRODUZIONE (TTS)...", flush=True)
    try:
        print("   Avvio di espeak-ng...", flush=True)
        subprocess.run(["espeak-ng", "-v", "it", "Test di riproduzione audio riuscito."], check=True)
        print("   [OK] Dovresti aver sentito la voce sintetica.", flush=True)
    except Exception as e:
        print(f"   [ERRORE] Riproduzione espeak-ng fallita: {e}", flush=True)

    # 2. Test di Registrazione
    print("\n2. Test di REGISTRAZIONE (Microfono)...", flush=True)
    sample_rate = 16000
    duration = 4.0 # secondi
    
    try:
        # Usa il dispositivo di default (che passa per plug -> dsnoop)
        print(f"   Inizio registrazione di {duration} secondi... PARLA ORA!", flush=True)
        recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
        sd.wait() # Attende il completamento della registrazione
        print("   Registrazione completata.", flush=True)
        
        # Converte l'array numpy in byte PCM
        raw_bytes = recording.tobytes()
        
        # Salva in formato WAV temporaneo
        output_file = "/tmp/test_joshua.wav"
        save_wav(output_file, raw_bytes, sample_rate)
        print(f"   [OK] Audio registrato salvato in: {output_file}", flush=True)
        
        # 3. Test di Riascolto
        print("\n3. Test di RIASCOLTO della tua voce...", flush=True)
        print("   Riproduzione del file registrato tramite aplay...", flush=True)
        subprocess.run(["aplay", output_file], check=True)
        print("   [OK] Riascolto completato.", flush=True)
        
    except Exception as e:
        print(f"   [ERRORE] Registrazione o riascolto fallito: {e}", flush=True)
        print("\nConsiglio: Se fallisce, verifica i log per vedere quale combinazione hardware funziona.", flush=True)

if __name__ == "__main__":
    main()
