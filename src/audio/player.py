import subprocess
import shutil
import queue
import threading
import time
import re

class TTSPlayer:
    def __init__(self, voice="it", pitch=30, speed=120):
        self.voice = voice
        self.pitch = pitch
        self.speed = speed
        self.espeak_exe = self._find_espeak()
        
        self.phrase_queue = queue.Queue()
        self.current_process = None
        self.playing_thread = None
        self.stop_event = threading.Event()
        self.is_playing = False
        self.thread_active = False

        if not self.espeak_exe:
            print("[WARNING] Sintetizzatore 'espeak-ng' o 'espeak' non trovato nel sistema. L'audio non verrà riprodotto.", flush=True)

    def _find_espeak(self):
        """Trova l'eseguibile di espeak nel PATH del sistema operativo (Windows/Linux)."""
        for cmd in ["espeak-ng", "espeak", "espeak-ng.exe", "espeak.exe"]:
            if shutil.which(cmd):
                return cmd
        return None

    def _play_worker(self):
        """Thread worker che consuma la coda di frasi e le riproduce una alla volta."""
        self.thread_active = True
        while not self.stop_event.is_set():
            try:
                # Prende la frase dalla coda con un timeout per controllare lo stop_event
                phrase = self.phrase_queue.get(timeout=0.2)
            except queue.Empty:
                if self.stop_event.is_set():
                    break
                continue

            if not self.espeak_exe:
                self.is_playing = True
                print(f"[Simulazione Voce Joshua]: {phrase}", flush=True)
                self.phrase_queue.task_done()
                self.is_playing = False
                continue

            # Rimuove caratteri speciali non pronunciabili
            clean_phrase = re.sub(r'[*_`#]', '', phrase).strip()
            if not clean_phrase:
                self.phrase_queue.task_done()
                continue

            # Costruisce il comando espeak-ng
            cmd = [
                self.espeak_exe,
                "-v", self.voice,
                "-p", str(self.pitch),
                "-s", str(self.speed),
                clean_phrase
            ]

            try:
                self.is_playing = True
                # Avvia il processo espeak-ng in background
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                # Attende il completamento della frase corrente
                self.current_process.wait()
            except Exception as e:
                print(f"Errore nella riproduzione TTS: {e}", flush=True)
            finally:
                self.current_process = None
                self.phrase_queue.task_done()
                self.is_playing = False

        self.thread_active = False

    def start(self):
        """Avvia il thread di riproduzione se non è già attivo."""
        if not self.thread_active:
            self.stop_event.clear()
            self.playing_thread = threading.Thread(target=self._play_worker, daemon=True)
            self.playing_thread.start()

    def stop(self):
        """Interrompe immediatamente qualsiasi riproduzione e svuota la coda."""
        print("[Joshua] Interruzione riproduzione audio in corso...", flush=True)
        self.stop_event.set()
        
        # Svuota la coda delle frasi da pronunciare
        while not self.phrase_queue.empty():
            try:
                self.phrase_queue.get_nowait()
                self.phrase_queue.task_done()
            except queue.Empty:
                break

        # Termina istantaneamente il processo espeak-ng corrente se attivo
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.kill()
            except ProcessLookupError:
                pass
            self.current_process = None

        if self.playing_thread:
            self.playing_thread.join(timeout=1.0)
            self.playing_thread = None
        
        self.is_playing = False
        self.thread_active = False

    def play_sync(self, text):
        """Riproduce un testo in modo sincrono (bloccante), utile per il boot."""
        self.stop() # Si assicura che non ci sia altro in coda
        if self.espeak_exe:
            try:
                subprocess.run([
                    self.espeak_exe,
                    "-v", self.voice,
                    "-p", str(self.pitch),
                    "-s", str(self.speed),
                    text
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Errore riproduzione sincrona: {e}", flush=True)
        else:
            print(f"[Simulazione Voce Joshua Sync]: {text}", flush=True)

    def enqueue_text_stream(self, text_stream_generator):
        """
        Riceve un generatore di token di testo (Gemini stream),
        accumula i token fino al raggiungimento di punteggiatura logica,
        e inserisce la frase nella coda del TTS per la lettura immediata.
        """
        self.start() # Avvia il thread se spento
        
        buffer = []
        # Punteggiatura che determina la fine di una frase logica
        sentence_endings = re.compile(r'[.,;:!?\n]')

        for token in text_stream_generator:
            if self.stop_event.is_set():
                break
            
            buffer.append(token)
            full_text = "".join(buffer)

            # Controlla se abbiamo completato una frase
            matches = list(sentence_endings.finditer(full_text))
            if matches:
                # Prende l'ultima punteggiatura trovata nel blocco attuale
                last_match_idx = matches[-1].end()
                phrase = full_text[:last_match_idx].strip()
                
                if phrase:
                    # Inserisce la frase completata nella coda del TTS
                    self.phrase_queue.put(phrase)
                
                # Tiene il resto nel buffer
                buffer = [full_text[last_match_idx:]]

        # Inserisce l'eventuale rimanenza alla fine dello stream
        remaining = "".join(buffer).strip()
        if remaining and not self.stop_event.is_set():
            self.phrase_queue.put(remaining)
