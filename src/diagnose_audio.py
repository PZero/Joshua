import os
import sys

def setup_audio_config():
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
        asound_content = f"""# Generato dinamicamente da Joshua (Diagnostica) con supporto dmix/dsnoop
pcm.!default {{
    type asym
    playback.pcm "playback"
    capture.pcm "capture"
}}

pcm.playback {{
    type plug
    slave.pcm "dmixed"
}}

pcm.capture {{
    type plug
    slave.pcm "array"
}}

pcm.dmixed {{
    type dmix
    slave.pcm "hw:{card_index},0"
    ipc_key 555555
    ipc_key_add_uid false
}}

pcm.array {{
    type dsnoop
    slave {{
        pcm "hw:{card_index},0"
        channels 2
    }}
    ipc_key 666666
    ipc_key_add_uid false
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

setup_audio_config()

import sounddevice as sd
import numpy as np

def test_device_configs(device_index, name):
    print(f"\n--- Test di configurazione per il dispositivo {device_index}: {name} ---", flush=True)
    rates = [8000, 16000, 32000, 44100, 48000]
    channels_options = [1, 2]
    dtypes = ['int16', 'int32', 'float32']
    
    success_count = 0
    for rate in rates:
        for channels in channels_options:
            for dtype in dtypes:
                try:
                    # Tenta di aprire l'input stream per verificare la compatibilità
                    stream = sd.InputStream(
                        device=device_index,
                        samplerate=rate,
                        channels=channels,
                        dtype=dtype
                    )
                    stream.start()
                    stream.stop()
                    stream.close()
                    print(f"  [SUCCESS] Rate: {rate}Hz, Channels: {channels}, Dtype: {dtype}", flush=True)
                    success_count += 1
                except Exception:
                    pass
    if success_count == 0:
        print("  [FAILED] Nessuna combinazione supportata trovata per questo dispositivo.", flush=True)

def main():
    print("==================================================", flush=True)
    print("         JOSHUA - AUDIO DIAGNOSTIC TOOL           ", flush=True)
    print("==================================================", flush=True)
    
    try:
        import os
        if os.path.exists("/etc/asound.conf"):
            print("\n--- Contenuto di /etc/asound.conf ---", flush=True)
            with open("/etc/asound.conf", "r") as f:
                print(f.read(), flush=True)
        else:
            print("\nFile /etc/asound.conf non trovato nel container.", flush=True)
    except Exception as e:
        print(f"Errore nella lettura di /etc/asound.conf: {e}", flush=True)
        
    try:
        devices = sd.query_devices()
        print("\n--- Elenco Dispositivi rilevati da sounddevice ---", flush=True)
        for i, dev in enumerate(devices):
            print(f"Index {i}: {dev['name']} (Max Inputs: {dev['max_input_channels']}, Max Outputs: {dev['max_output_channels']})", flush=True)
            
        print("\nAvvio test sistematico di acquisizione...", flush=True)
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                test_device_configs(i, dev['name'])
                
        # Test anche per il dispositivo di default (None)
        test_device_configs(None, "Default (None)")
                
    except Exception as e:
        print(f"Errore generale durante la diagnostica: {e}", flush=True)

if __name__ == "__main__":
    main()
