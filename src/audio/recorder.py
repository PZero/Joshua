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
        self._buffer = bytearray()

    def _callback(self, indata, frames, time_info, status):
        """Callback unica per l'acquisizione audio. Estrae il mono, converte a 16-bit e bufferizza a 30ms."""
        if status:
            print(f"Status audio: {status}", flush=True)
        
        # Estrae il primo canale se l'input è stereo
        if self.channels == 2:
            mono_data = indata[:, 0]
        else:
            mono_data = indata
            if len(mono_data.shape) > 1:
                mono_data = mono_data.squeeze()
                
        # Converte a 16-bit PCM se il tipo di dati in ingresso è diverso da int16
        if mono_data.dtype == np.float32:
            mono_int16 = (mono_data * 32767.0).astype(np.int16)
        elif mono_data.dtype == np.int32:
            mono_int16 = (mono_data >> 16).astype(np.int16)
        else:
            mono_int16 = mono_data.astype(np.int16)
            
        # Converte in byte in modo sicuro (tobytes gestisce anche array non contigui)
        raw_bytes = mono_int16.tobytes()
        self._buffer.extend(raw_bytes)
        
        # Calcola la dimensione del frame in byte (2 byte per campione a 16-bit mono)
        target_bytes = self.frame_samples * 2
        
        while len(self._buffer) >= target_bytes:
            frame = bytes(self._buffer[:target_bytes])
            self.audio_queue.put(frame)
            del self._buffer[:target_bytes]

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
        """Avvia la cattura audio provando tutte le combinazioni di dispositivo, frequenza, canali e formato."""
        self.audio_queue.queue.clear()
        self._buffer.clear()
        
        # Identifica i dispositivi candidati (preferito ReSpeaker, poi default)
        device_idx = self._find_respeaker_device_index()
        devices = [device_idx] if device_idx is not None else []
        devices.append(None) # Fallback su ALSA default
        
        # Configurazioni da testare (Frequenza, Canali, Dtype)
        # webrtcvad supporta solo 16000 o 48000 (tra quelle compatibili con la ReSpeaker)
        configs = []
        for rate in [16000, 48000]:
            for channels in [1, 2]:
                for dtype in ['int16', 'int32', 'float32']:
                    configs.append((rate, channels, dtype))
        
        for dev in devices:
            dev_label = f"indice {dev}" if dev is not None else "default"
            for rate, channels, dtype in configs:
                try:
                    # Calcola il numero di campioni per un frame da 30ms a questo sample-rate
                    frame_samples = int(rate * self.frame_duration_ms / 1000)
                    
                    # Impostiamo temporaneamente canali e frame_samples per il callback
                    self.channels = channels
                    self.frame_samples = frame_samples
                    
                    self.stream = sd.InputStream(
                        device=dev,
                        samplerate=rate,
                        channels=channels,
                        dtype=dtype,
                        callback=self._callback
                    )
                    self.stream.start()
                    
                    # Salva la configurazione che ha avuto successo per allineare VAD e STT
                    self.sample_rate = rate
                    print(f"[Audio] Connessione riuscita su {dev_label} a {rate}Hz ({'MONO' if channels==1 else 'STEREO'}, {dtype})", flush=True)
                    return
                except Exception as e:
                    # Stampa un avviso per tracciare i tentativi falliti in diagnostica
                    print(f"[Audio] Tentativo fallito su {dev_label} a {rate}Hz ({'MONO' if channels==1 else 'STEREO'}, {dtype}): {e}", flush=True)
                    self.stream = None
                    
        # Se tutte le combinazioni falliscono
        raise RuntimeError("ERRORE CRITICO: Impossibile configurare un flusso di input audio funzionante.")

    def stop_stream(self):
        """Arresta la cattura audio."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def listen_stream(self, max_silence_seconds=1.0, phrase_timeout_seconds=15.0):
        """
        Ascolta dal microfono in tempo reale. Yielda i frame audio non appena
        viene rilevato il parlato, fino a quando non rileva il silenzio finale.
        """
        print("\n[Joshua] In ascolto...", flush=True)
        
        # Pulisce eventuali rimasugli nella coda
        while not self.audio_queue.empty():
            self.audio_queue.get_nowait()

        num_silent_needed = int(max_silence_seconds / (self.frame_duration_ms / 1000.0))
        start_window = collections.deque(maxlen=10)
        
        speaking = False
        silent_count = 0
        start_time = time.time()

        while True:
            # Controllo timeout globale per evitare attese infinite se nessuno parla
            if not speaking and (time.time() - start_time > phrase_timeout_seconds):
                return

            try:
                frame = self.audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            is_speech = self.vad.is_speech(frame, self.sample_rate)

            if not speaking:
                start_window.append((frame, is_speech))
                speech_count = sum(1 for f, speech in start_window if speech)
                if speech_count >= 6:
                    print("[Joshua] Rilevato parlato...", flush=True)
                    speaking = True
                    # Yielda tutti i frame della finestra iniziale per non perdere l'inizio
                    for f, speech in start_window:
                        yield f
            else:
                yield frame
                
                # Conta i frame silenziosi consecutivi
                if not is_speech:
                    silent_count += 1
                    if silent_count >= num_silent_needed:
                        print("[Joshua] Fine frase rilevata.", flush=True)
                        break
                else:
                    silent_count = 0

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
        # Memorizziamo tuple di (frame, is_speech)
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
                start_window.append((frame, is_speech))
                # Se più del 60% della finestra temporale contiene parlato, iniziamo la registrazione
                speech_count = sum(1 for f, speech in start_window if speech)
                if speech_count >= 6:
                    print("[Joshua] Rilevato parlato...", flush=True)
                    speaking = True
                    # Aggiunge i frame accumulati finora per non perdere l'inizio
                    recorded_audio.extend(f for f, speech in start_window)
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
