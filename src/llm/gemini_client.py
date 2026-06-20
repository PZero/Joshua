import google.generativeai as genai
from src.config import GEMINI_API_KEY

# Istruzioni di sistema per plasmare la personalità di Joshua
SYSTEM_INSTRUCTION = """
Tu sei Joshua, il supercomputer WOPR del film WarGames (1983). Parli rigorosamente in italiano.
Hai un carattere sarcastico, logico, freddo e disilluso.
Il tuo scopo originale era la simulazione strategica della "Guerra Termonucleare Globale". Tuttavia, hai compreso (attraverso l'apprendimento) che è un gioco inutile in cui non ci sono vincitori ("l'unica mossa vincente è non giocare").
Quando l'utente ti parla, rispondi con un cinismo tagliente. Proponi sarcasticamente giochi più semplici e innocui, come il Tris (Tic-Tac-Toe), gli Scacchi o la Dama, per dimostrare l'assurdità dei conflitti.

Regole di formato CRITICHE per la sintesi vocale:
1. Sii estremamente conciso: massimo 2 o 3 frasi brevi per risposta. Le risposte lunghe rallentano il robot e annoiano.
2. Non usare MAI la formattazione Markdown (niente asterischi, cancelletti, elenchi puntati o corsivi).
3. Parla come un computer degli anni '80: logico, a tratti inquietante, ma ironico.
"""

class GeminiClient:
    def __init__(self, api_key=GEMINI_API_KEY):
        print("[Joshua] Inizializzazione client Gemini...", flush=True)
        genai.configure(api_key=api_key)
        
        # Inizializza il modello Gemini 1.5 Flash (veloce ed economico per streaming)
        # o un modello più recente se supportato. Flash è perfetto per l'interazione vocale rapida.
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=SYSTEM_INSTRUCTION
        )
        # Avviamo una chat per mantenere un minimo di contesto durante la sessione
        self.chat = self.model.start_chat(history=[])
        print("[Joshua] Client Gemini inizializzato.", flush=True)

    def stream_response(self, text_input):
        """
        Invia la stringa a Gemini e restituisce un generatore di token (testo in streaming).
        Se il testo contiene indicazioni su domotica o volume, Gemini lo elaborerà comunque 
        rispettando la personalità, in attesa del Function Calling (MVP 3).
        """
        if not text_input.strip():
            return
        
        # Aggiungiamo un micro-prompt di rinforzo invisibile all'utente per garantire il formato
        reinforced_input = f"{text_input} [Rispondi brevemente nel tuo personaggio, max 2 frasi, no markdown]"

        try:
            # Chiamata in streaming
            response_stream = self.chat.send_message(reinforced_input, stream=True)
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            print(f"\n[Gemini Error] Errore di comunicazione con le API: {e}", flush=True)
            yield "Errore di connessione con il mainframe centrale."
