FROM python:3.10-slim

# Installa le dipendenze di sistema necessarie per Audio, PortAudio, GPIO e espeak-ng
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    portaudio19-dev \
    libasound2-dev \
    alsa-utils \
    espeak-ng \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia requirements.txt e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice dell'applicazione
COPY src/ ./src/

# Forza Python ad inviare l'output a schermo immediatamente (utile per i log in tempo reale)
ENV PYTHONUNBUFFERED=1

# Avvia l'orchestratore principale
CMD ["python", "-m", "src.main"]
