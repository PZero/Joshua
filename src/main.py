import os
import sys
import time

def setup_audio_config():
    # Cerca la scheda seeed2micvoicec o wm8960 in /proc/asound/cards
    card_index = None
    if os.path.exists("/proc/asound/cards"):
        try:
            with open("/proc/asound/cards", "r") as f:
                content = f.read()
            for line in content.splitlines():
                line = line.strip()
                if "seeed2micvoicec" in line.lower() or "wm8960" in line.lower():
                    parts = line.split("[")
                    if parts:
                        idx_str = parts[0].strip()
                        if idx_str.isdigit():
                            card_index = int(idx_str)
                            break
        except Exception as e:
            print(f"[Audio Warning] Errore nella lettura di /proc/asound/cards: {e}", flush=True)
            
    if card_index is not None:
        asound_content = f"""# Generato dinamicamente da Joshua
pcm.!default {{
    type plug
    slave {{
        pcm "hw:{card_index},0"
        channels 2
    }}
}}
"""
        try:
            with open("/etc/asound.conf", "w") as f:
                f.write(asound_content)
            print(f"[Audio] Generato /etc/asound.conf per la scheda audio indice {card_index}", flush=True)
        except Exception as e:
            print(f"[Audio Warning] Impossibile scrivere /etc/asound.conf: {e}", flush=True)
    else:
        print("[Audio Warning] Scheda seeed2micvoicec/wm8960 non trovata in /proc/asound/cards. Verranno usati i default di sistema.", flush=True)

# Esegui la configurazione prima di caricare le librerie audio
setup_audio_config()

import threading
from src.audio.recorder import AudioRecorder
from src.audio.player import TTSPlayer
from src.stt.vosk_client import VoskSTT
from src.llm.gemini_client import GeminiClient

def main():
    print("==================================================", flush=True)
    print("       JOSHUA - SYSTEM INITIALIZATION             ", flush=True)
    print("==================================================", flush=True)
    
    # Diagnostica temporanea per stampare i dispositivi audio visti all'interno di Docker
    try:
        import sounddevice as sd
        print("\n[DIAGNOSTICA] Dispositivi audio rilevati nel container:\n", sd.query_devices(), flush=True)
    except Exception as diag_err:
        print(f"\n[DIAGNOSTICA ERROR] Errore di query: {diag_err}", flush=True)

    # 1. Inizializzazione di tutti i moduli a livelli
    try:
        recorder = AudioRecorder()
        player = TTSPlayer()
        stt = VoskSTT()
        gemini = GeminiClient()
    except FileNotFoundError as fnf:
        print(f"\n[VOSK ERROR] Modello non trovato: {fnf}", flush=True)
        print("Assicurati di installare il modello Vosk prima di eseguire lo script sul Raspberry Pi.", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Errore durante l'inizializzazione: {e}", flush=True)
        sys.exit(1)

    # 2. Il Momento Wow (Boot drammatico)
    print("\n[System] Esecuzione boot di sistema...", flush=True)
    time.sleep(3.0)  # Simulazione caricamento mainframe anni '80
    player.play_sync("Salve professore. Vuole giocare una partita?")
    print("[Joshua] Pronto per le interazioni.", flush=True)

    # Avvia la registrazione audio continua in background
    try:
        recorder.start_stream()
        stt.sample_rate = recorder.sample_rate
        print(f"[Joshua] Frequenza STT allineata a: {stt.sample_rate}Hz", flush=True)
    except RuntimeError as re:
        print(f"\n[AUDIO CRITICAL ERROR] {re}", flush=True)
        print("Il container rimarrà attivo per consentire la diagnostica.", flush=True)
        print("Esegui: docker exec -it joshua_assistant python -m src.diagnose_audio", flush=True)
        while True:
            time.sleep(10)

    try:
        while True:
            # Ascolta finché l'utente non finisce di parlare
            audio_bytes = recorder.listen_until_silence()
            if not audio_bytes:
                continue

            # Trascrizione locale
            text = stt.transcribe(audio_bytes)
            if not text.strip():
                continue

            # Evento per segnalare l'interruzione al monitor del barge-in
            stop_barge_in_monitor = threading.Event()
            interrupted = False

            def trigger_barge_in():
                nonlocal interrupted
                interrupted = True
                player.stop()  # Ferma immediatamente il processo espeak in esecuzione e svuota la coda
                stop_barge_in_monitor.set()

            # Avvia la generazione in streaming da Gemini
            response_generator = gemini.stream_response(text)
            
            # Thread parallelo che scarica lo stream di Gemini e riempie la coda del TTS
            stream_thread = threading.Thread(
                target=player.enqueue_text_stream,
                args=(response_generator,),
                daemon=True
            )
            stream_thread.start()

            # Piccolo delay per permettere allo stream e al player di inizializzarsi
            time.sleep(0.15)

            # Monitoriamo il barge-in solo mentre Joshua sta parlando o sta ricevendo dati
            while (player.is_playing or not player.phrase_queue.empty() or stream_thread.is_alive()) and not stop_barge_in_monitor.is_set():
                recorder.monitor_for_barge_in(
                    on_barge_in_callback=trigger_barge_in,
                    stop_event=stop_barge_in_monitor
                )
                time.sleep(0.05)

            # Chiude il monitor in ogni caso
            stop_barge_in_monitor.set()
            stream_thread.join(timeout=0.5)

            if interrupted:
                print("[System] Joshua interrotto dall'utente. Ripristino ascolto immediato...", flush=True)
                # Diamo un piccolo respiro al sistema prima di riattivare l'ascolto
                time.sleep(0.2)

    except KeyboardInterrupt:
        print("\n[System] Arresto controllato richiesto dall'utente.", flush=True)
    finally:
        # Pulisce i dispositivi audio
        recorder.stop_stream()
        player.stop()
        print("[System] Arresto completato. Addio professore.", flush=True)

if __name__ == "__main__":
    main()
