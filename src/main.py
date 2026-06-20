import time
import threading
import sys
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
    recorder.start_stream()

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
