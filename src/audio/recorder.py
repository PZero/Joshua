import queue
import time
import collections
import sounddevice as sd
import numpy as np
import webrtcvad
from src.config import AUDIO_SAMPLE_RATE, AUDIO_CHANNELS

class AudioRecorder:
    def __init__(self, sample_rate=AUDIO_SAMPLE_RATE, vad_mode=3):
        self.sample_rate = sample_rate
        self.channels = AUDIO_CHANNELS
        self.vad = webrtcvad.Vad(vad_mode)
        
        # webrtcvad accetta solo frame di 10, 20 o 30 ms
        self.frame_duration_ms = 30
        # Campioni per frame: 16000 * 0.030 = 480 campioni (960 byte in 16-bit mono)
        self.frame_samples = int(self.sample_rate * self.frame_duration_ms / 1000)
        self.audio_queue = queue.Queue()
        self.stream = None

    def _callback_mono(self, indata, frames, time_info, status):
        """Callback per input mono (1 canale)."""
        if status:
            print(f"Status audio: {status}", flush=True)
        # indata è un array di forma (samples, 1). Lo inseriamo direttamente convertendolo in byte
        self.audio_queue.put(bytes(indata))

    def _callback_stereo(self, indata, frames, time_info, status):
        """Callback per input stereo (2 canali). Estrae solo il primo canale."""
        if status:
            print(f"Status audio: {status}", flush=True)
        # Estraiamo solo il primo canale (mono) per webrtcvad e Vosk
        mono_data = indata[:, 0]
        self.audio_queue.put(bytes(mono_data))

    def _find_respeaker_device_index(self):
        """Scansiona i dispositivi PortAudio per trovare l'indice del ReSpeaker HAT."""
        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                name = dev.get('name', '').lower()
                if "seeed" in name or "wm8960" in name:
                    if dev.get('max_input_channels', 0) > 0:
                        return idx
        except Exception as e:
            print(f"[Audio] Errore nella ricerca dei dispositivi audio: {e}", flush=True)
        return None

    def start_stream(self):
        """Avvia la cattura audio continua dal microfono con logica di fallback a cascata."""
        self.audio_queue.queue.clear()
        
        # Tentativo 1: Default Mono (Sfrutta /etc/asound.conf montato per fare rate-conversion a 16kHz)
        try:
            print("[Audio] Tentativo 1: Apertura dispositivo di default in modalità MONO...", flush=True)
            self.stream = sd.InputStream(
                device=None,
                samplerate=self.sample_rate,
                channels=1,
                dtype='int16',
                blocksize=self.frame_samples,
                callback=self._callback_mono
            )
            self.stream.start()
            print("[Audio] Connesso con successo al dispositivo predefinito (MONO).", flush=True)
            return
        except Exception as e:
            print(f"[Audio] Tentativo 1 fallito (Default Mono): {e}", flush=True)

        # Tentativo 2: Default Stereo (Alcune configurazioni ALSA richiedono stereo anche nel plug)
        try:
            print("[Audio] Tentativo 2: Apertura dispositivo di default in modalità STEREO...", flush=True)
            self.stream = sd.InputStream(
                device=None,
                samplerate=self.sample_rate,
                channels=2,
                dtype='int16',
                blocksize=self.frame_samples,
                callback=self._callback_stereo
            )
            self.stream.start()
            print("[Audio] Connesso con successo al dispositivo predefinito (STEREO).", flush=True)
            return
        except Exception as e:
            print(f"[Audio] Tentativo 2 fallito (Default Stereo): {e}", flush=True)

        # Tentativo 3: Hardware ReSpeaker Diretto (Bypassa ALSA default e interroga direttamente l'hardware)
        device_idx = self._find_respeaker_device_index()
        if device_idx is not None:
            try:
                print(f"[Audio] Tentativo 3: Apertura hardware ReSpeaker diretto (indice {device_idx}, STEREO)...", flush=True)
                self.stream = sd.InputStream(
                    device=device_idx,
                    samplerate=self.sample_rate,
                    channels=2,
                    dtype='int16',
                    blocksize=self.frame_samples,
                    callback=self._callback_stereo
                )
                self.stream.start()
                print("[Audio] Connesso con successo all'hardware ReSpeaker (STEREO).", flush=True)
                return
            except Exception as e:
                print(f"[Audio] Tentativo 3 fallito (Hardware Diretto): {e}", flush=True)

        # Se tutti i tentativi falliscono
        raise RuntimeError("ERRORE CRITICO: Impossibile aprire un flusso di acquisizione audio valido.")

    def stop_stream(self):
        """Arresta la cattura audio."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def listen_until_silence(self, max_silence_seconds=1.0, phrase_timeout_seconds=15.0):
        """
        Ascolta dal microfono finché non rileva che l'utente ha iniziato a parlare
        e successivamente ha smesso, rimanendo in silenzio per 'max_silence_seconds'.
        """
        print("\n[Joshua] In ascolto...", flush=True)
        
        # Pulisce eventuali rimasugli nella coda
        while not self.audio_queue.empty():
            self.audio_queue.get_nowait()

        # Parametri di controllo
        num_silent_needed = int(max_silence_seconds / (self.frame_duration_ms / 1000.0))
        
        # Buffer circolare per rilevare l'inizio della frase (10 frame = 300ms)
        start_window = collections.deque(maxlen=10)
        
        speaking = False
        recorded_audio = []
        silent_count = 0
        start_time = time.time()

        while True:
            # Controllo timeout globale per evitare attese infinite se nessuno parla
            if not speaking and (time.time() - start_time > phrase_timeout_seconds):
                return None

            try:
                # Prendi il prossimo chunk audio (blocco da 30ms)
                frame = self.audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            # Valuta se il frame contiene voce (1 = voce, 0 = silenzio/rumore)
            is_speech = self.vad.is_speech(frame, self.sample_rate)

            if not speaking:
                # Determina se l'utente ha iniziato a parlare
                start_window.append(is_speech)
                # Se più del 60% della finestra temporale contiene parlato, iniziamo la registrazione
                if sum(start_window) >= 6:
                    print("[Joshua] Rilevato parlato...", flush=True)
                    speaking = True
                    # Aggiunge i frame accumulati finora per non perdere l'inizio
                    recorded_audio.extend(start_window)
            else:
                recorded_audio.append(frame)
                
                # Conta i frame silenziosi consecutivi per capire quando l'utente si ferma
                if not is_speech:
                    silent_count += 1
                    if silent_count >= num_silent_needed:
                        print("[Joshua] Fine frase rilevata.", flush=True)
                        break
                else:
                    silent_count = 0

        # Concatena tutti i frame in un unico array di byte PCM
        return b"".join(recorded_audio) if recorded_audio else None

    def monitor_for_barge_in(self, on_barge_in_callback, stop_event):
        """
        Monitora l'ingresso audio mentre Joshua sta parlando.
        Se rileva parlato umano per almeno 150ms, invoca 'on_barge_in_callback'.
        """
        # Buffer circolare per evitare falsi positivi (5 frame = 150ms)
        barge_in_window = collections.deque(maxlen=5)
        
        # Pulisce la coda
        while not self.audio_queue.empty():
            self.audio_queue.get_nowait()

        while not stop_event.is_set():
            try:
                frame = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            is_speech = self.vad.is_speech(frame, self.sample_rate)
            barge_in_window.append(is_speech)

            # Se 4 dei 5 frame contengono parlato, l'utente sta interrompendo
            if sum(barge_in_window) >= 4:
                print("\n[Barge-in] Rilevata interruzione vocale dall'utente!", flush=True)
                on_barge_in_callback()
                break
