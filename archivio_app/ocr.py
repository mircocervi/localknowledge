"""OCR delle pagine scansionate.

Due motori, scelti in /admin:
- tesseract: Tesseract con il dizionario italiano. Veloce e già installato.
- visione: un modello che "vede" le immagini (per esempio Unlimited OCR di Baidu o
  qwen3.6 in LM Studio), chiamato in locale con l'API compatibile OpenAI.
"""
import base64
import io
import shutil
import subprocess

import httpx

from . import config

PROMPT_VISIONE = (
    "Trascrivi fedelmente tutto il testo di questa pagina, nell'ordine di lettura. "
    "Non riassumere, non commentare, non tradurre. Rispondi solo con il testo."
)


def tesseract_disponibile() -> bool:
    return shutil.which("tesseract") is not None


def ocr_immagine(immagine, impostazioni: dict | None = None) -> str:
    """immagine: PIL.Image. Restituisce il testo riconosciuto."""
    imp = (impostazioni or config.leggi())["ocr"]
    if imp.get("motore") == "visione" and imp.get("modello"):
        return _ocr_visione(immagine, imp)
    return _ocr_tesseract(immagine, imp.get("lingua") or "ita")


def _png(immagine) -> bytes:
    buf = io.BytesIO()
    immagine.save(buf, format="PNG")
    return buf.getvalue()


def _ocr_tesseract(immagine, lingua: str) -> str:
    if not tesseract_disponibile():
        raise RuntimeError("Tesseract non è installato: brew install tesseract tesseract-lang")
    r = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", lingua, "--psm", "3"],
        input=_png(immagine), capture_output=True, timeout=180,
    )
    if r.returncode != 0:
        raise RuntimeError("Tesseract: " + r.stderr.decode("utf-8", "replace").strip()[:300])
    return r.stdout.decode("utf-8", "replace")


def _ocr_visione(immagine, imp: dict) -> str:
    fornitore = config.FORNITORI.get(imp.get("fornitore") or "lmstudio")
    if not fornitore or not fornitore["locale"]:
        raise RuntimeError("L'OCR con modello di visione si fa solo in locale (Ollama o LM Studio).")
    dati = base64.b64encode(_png(immagine)).decode()
    r = httpx.post(
        fornitore["url"] + "/chat/completions",
        json={
            "model": imp["modello"],
            "temperature": 0,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT_VISIONE},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + dati}},
            ]}],
        },
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"].get("content") or ""
