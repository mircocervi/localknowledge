"""Percorsi e impostazioni. Le impostazioni stanno in indice/impostazioni.json, mai nel codice."""
import copy
import json
import os
import threading
import uuid
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
DIR_INDICE = Path(os.environ.get("ARCHIVIO_INDICE", RADICE / "indice"))
FILE_DB = DIR_INDICE / "archivio.db"
FILE_IMPOSTAZIONI = DIR_INDICE / "impostazioni.json"
DIR_WEB = RADICE / "web"

ESTENSIONI = {".pdf", ".docx", ".txt", ".md", ".markdown", ".csv"}

FORNITORI = {
    "ollama": {"nome": "Ollama", "url": "http://localhost:11434/v1", "locale": True},
    "lmstudio": {"nome": "LM Studio", "url": "http://localhost:1234/v1", "locale": True},
    "openrouter": {"nome": "OpenRouter", "url": "https://openrouter.ai/api/v1", "locale": False},
}

DOMANDE_ESEMPIO = [
    "Il contratto Nordwand in vigore cosa prevede se cambia il controllo di Crinale?",
    "Ci sono cause in corso contro Crinale?",
    "Qual è il fatturato di Crinale in Germania?",
]

# Vocabolario dei sinonimi per la ricerca per parole: una riga, un gruppo. Si modifica da /admin.
SINONIMI = [
    "causa, cause, contenzioso, ricorso, tribunale, giudizio, lite, controversia, vertenza, citazione, decreto ingiuntivo",
    "fatturato, ricavi, vendite, giro d'affari",
    "recesso, disdetta, risoluzione, scioglimento",
    "affitto, locazione, canone, pigione",
    "dipendenti, personale, organico, addetti",
    "utile, risultato, perdita",
    "debiti, finanziamento, mutuo, prestito",
    "magazzino, deposito, stoccaggio",
    "amministratore, presidente, consiglio, cda",
    "socio, soci, quote, partecipazione",
]

PREDEFINITE = {
    "cartelle": [],
    "fornitore": "ollama",
    "modello": "hf.co/XHToken/Spark-X2.5-4B-GGUF:Q8_0",
    "ragionamento": False,  # con tutto l'archivio Spark fa 3/3 anche senza ragionare, ed è molto più veloce
    "preferiti": {  # l'ultimo modello scelto per ogni fornitore: cambiando scheda si riparte da lì
        "ollama": "hf.co/XHToken/Spark-X2.5-4B-GGUF:Q8_0",
        "lmstudio": "minicpm5-2b",
        "openrouter": "qwen/qwen3.8-27b:free",
    },
    "modo": "auto",  # auto: tutto l'archivio se entra nel contesto del modello, altrimenti ricerca (RAG)
    "embedding": {"url": "http://localhost:11434", "modello": "qwen3-embedding:0.6b"},
    "ocr": {"motore": "tesseract", "lingua": "ita", "fornitore": "lmstudio", "modello": ""},
    "ricerca": {"estratti": 8, "candidati": 40, "limite_tutto": 60000, "limite_ricerca": 14000},
    "pezzi": {"dimensione": 1000, "sovrapposizione": 150},
    "moduli": {"bi": False},
    "domande_esempio": DOMANDE_ESEMPIO,
    "sinonimi": SINONIMI,
    "mcp_esterni": [
        {
            "id": "crinale-duckdb",
            "nome": "Crinale MCP (dati DuckDB)",
            "url": "http://127.0.0.1:5400/mcp",
            "descrizione": "Database DuckDB di Crinale in sola lettura. Sarà la fonte dati del modulo BI.",
            "avvio": "uv run server_mcp_http.py (in corso/L05-chat-unica/mcp-unsloth)",
        }
    ],
}

_lock = threading.RLock()


def _unisci(base: dict, sopra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in sopra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _unisci(out[k], v)
        else:
            out[k] = v
    return out


def leggi() -> dict:
    with _lock:
        try:
            dati = json.loads(FILE_IMPOSTAZIONI.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            dati = {}
        return _unisci(PREDEFINITE, dati)


def scrivi(dati: dict) -> None:
    with _lock:
        DIR_INDICE.mkdir(parents=True, exist_ok=True)
        tmp = FILE_IMPOSTAZIONI.with_suffix(".tmp")
        tmp.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(FILE_IMPOSTAZIONI)


def aggiorna(**campi) -> dict:
    with _lock:
        dati = leggi()
        for k, v in campi.items():
            if isinstance(v, dict) and isinstance(dati.get(k), dict):
                dati[k] = _unisci(dati[k], v)
            else:
                dati[k] = v
        scrivi(dati)
        return dati


def nuovo_id() -> str:
    return uuid.uuid4().hex[:8]


def chiave_openrouter() -> str | None:
    """La chiave arriva solo dall'ambiente (o da un file .env accanto all'app, fuori da git)."""
    chiave = os.environ.get("OPENROUTER_API_KEY")
    if chiave:
        return chiave.strip()
    env = RADICE / ".env"
    if env.exists():
        for riga in env.read_text(encoding="utf-8").splitlines():
            if riga.strip().startswith("OPENROUTER_API_KEY="):
                return riga.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None
