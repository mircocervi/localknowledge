"""Vettori (embedding), calcolati SEMPRE in locale con Ollama.

Un vettore è una lista di 1.024 numeri che rappresenta il significato di un testo.
Testi con significato simile hanno vettori vicini, anche se usano parole diverse
("recesso" e "disdetta"). La vicinanza si misura con la similarità del coseno.
"""
import httpx
import numpy as np

from . import config

ISTRUZIONE_DOMANDA = "Instruct: Given a question in Italian, retrieve the document passages that answer it\nQuery: "


class VettoriNonDisponibili(RuntimeError):
    pass


def _imp():
    return config.leggi()["embedding"]


def calcola(testi: list[str], domanda: bool = False, lotto: int = 32) -> np.ndarray:
    """Restituisce una matrice (n, d) di vettori normalizzati (lunghezza 1)."""
    imp = _imp()
    if domanda:
        testi = [ISTRUZIONE_DOMANDA + t for t in testi]
    risultati = []
    try:
        with httpx.Client(timeout=120) as c:
            for i in range(0, len(testi), lotto):
                r = c.post(imp["url"] + "/api/embed", json={"model": imp["modello"], "input": testi[i:i + lotto], "keep_alive": "2h"})
                if r.status_code == 404:
                    raise VettoriNonDisponibili(
                        f"Il modello {imp['modello']} non è in Ollama: ollama pull {imp['modello']}")
                r.raise_for_status()
                risultati.extend(r.json()["embeddings"])
    except httpx.ConnectError as e:
        raise VettoriNonDisponibili("Ollama non risponde su " + imp["url"] + ": avvialo (app Ollama).") from e
    m = np.asarray(risultati, dtype=np.float32)
    if m.size == 0:
        return m.reshape(0, 0)
    m /= np.linalg.norm(m, axis=1, keepdims=True) + 1e-12
    return m


def similarita(a: str, b: str) -> float:
    v = calcola([a, b])
    return float(v[0] @ v[1])
