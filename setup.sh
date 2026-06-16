#!/bin/bash
# Script di installazione per il Progetto Joshua (Raspberry Pi)

# Colori per i log a schermo
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Nessun colore

echo -e "${GREEN}=================================================="
echo -e "       JOSHUA BOOTSTRAPPER & INSTALLER            "
echo -e "==================================================${NC}"

# 1. Verifica ed installa Docker
if ! [ -x "$(command -v docker)" ]; then
    echo -e "${YELLOW}[!] Docker non è installato. Installazione in corso...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${GREEN}[+] Docker installato con successo.${NC}"
else
    echo -e "${GREEN}[+] Docker è già installato.${NC}"
fi

# 2. Verifica docker-compose
if ! [ -x "$(command -v docker-compose)" ]; then
    echo -e "${YELLOW}[!] docker-compose non trovato. Installazione in corso...${NC}"
    sudo apt-get update
    sudo apt-get install -y docker-compose
    echo -e "${GREEN}[+] docker-compose installato.${NC}"
else
    echo -e "${GREEN}[+] docker-compose è già installato.${NC}"
fi

# 3. Creazione guidata del file .env per le credenziali
if [ ! -f .env ]; then
    echo -e "${YELLOW}[!] File .env non trovato. Creazione guidata...${NC}"
    read -p "Inserisci la tua API KEY di Google Gemini: " gemini_key
    cp .env.example .env
    # Sostituisce il segnaposto con la chiave reale inserita dall'utente
    sed -i "s/your_gemini_api_key_here/$gemini_key/g" .env
    echo -e "${GREEN}[+] File .env creato correttamente.${NC}"
else
    echo -e "${GREEN}[+] File .env esistente rilevato.${NC}"
fi

# 4. Scaricamento ed estrazione automatica del modello di trascrizione vocale Vosk (Italiano Small)
MODEL_DIR="model"
MODEL_NAME="vosk-model-small-it-0.22"
if [ ! -d "$MODEL_DIR/$MODEL_NAME" ]; then
    echo -e "${YELLOW}[!] Modello Vosk locale non trovato. Scaricamento in corso (modello italiano small)...${NC}"
    mkdir -p $MODEL_DIR
    wget https://alphacephei.com/vosk/models/$MODEL_NAME.zip -O $MODEL_DIR/$MODEL_NAME.zip
    
    echo -e "${YELLOW}[!] Estrazione del modello...${NC}"
    unzip $MODEL_DIR/$MODEL_NAME.zip -d $MODEL_DIR/
    rm $MODEL_DIR/$MODEL_NAME.zip
    echo -e "${GREEN}[+] Modello Vosk configurato in $MODEL_DIR/$MODEL_NAME.${NC}"
else
    echo -e "${GREEN}[+] Modello Vosk già presente.${NC}"
fi

# 5. Avviso importante sui driver della scheda audio (ReSpeaker HAT)
echo -e "\n${YELLOW}[!] NOTA IMPORTANTE SUI DRIVER HARDWARE:${NC}"
echo -e "Affinché Docker possa accedere alla scheda audio ReSpeaker, devi installare i driver sul sistema operativo HOST."
echo -e "Se non lo hai già fatto, esegui questi comandi sul Raspberry Pi prima di procedere:"
echo -e "  git clone https://github.com/respeaker/seeed-voicecard.git"
echo -e "  cd seeed-voicecard"
echo -e "  sudo ./install.sh"
echo -e "  sudo reboot"

# 6. Build ed esecuzione del container
echo -e "\n${GREEN}[+] Compilazione ed avvio del container tramite docker-compose...${NC}"
docker-compose up --build -d

echo -e "\n${GREEN}=================================================="
echo -e "   Installazione completata! Joshua è in esecuzione."
echo -e "   Visualizza i log in tempo reale con:"
echo -e "   docker logs -f joshua_assistant"
echo -e "==================================================${NC}"
