"""I modelli che rispondono. Per tutti la stessa API compatibile OpenAI: cambia solo indirizzo e modello."""
import json
import re
import time

import httpx

from . import config

ESCLUDI_CHAT = re.compile(r"embed|embedding|rerank|bge-|nomic-bert|whisper", re.I)


def _base(fornitore: str) -> str:
    return config.FORNITORI[fornitore]["url"]


def _intestazioni(fornitore: str) -> dict:
    h = {"Content-Type": "application/json"}
    if fornitore == "openrouter":
        chiave = config.chiave_openrouter()
        if chiave:
            h["Authorization"] = f"Bearer {chiave}"
        h["HTTP-Referer"] = "http://127.0.0.1:4100"
        h["X-Title"] = "Archivio (locale)"
    return h


def elenco(fornitore: str, timeout: float = 4) -> dict:
    """Modelli disponibili su quel server. Non solleva eccezioni: restituisce {'acceso': False, 'errore': ...}."""
    if fornitore not in config.FORNITORI:
        return {"acceso": False, "errore": "fornitore sconosciuto", "modelli": []}
    try:
        if fornitore == "ollama":
            r = httpx.get(_base("ollama").removesuffix("/v1") + "/api/tags", timeout=timeout)
            r.raise_for_status()
            modelli = []
            for m in r.json().get("models", []):
                det = m.get("details") or {}
                if ESCLUDI_CHAT.search(m["name"]) or "bert" in (det.get("family") or ""):
                    continue
                modelli.append({"id": m["name"], "nome": m["name"], "dimensione": m.get("size"),
                                "parametri": det.get("parameter_size"), "quantizzazione": det.get("quantization_level"),
                                "famiglia": det.get("family")})
            return {"acceso": True, "modelli": modelli}
        if fornitore == "lmstudio":
            base = _base("lmstudio").removesuffix("/v1")
            try:
                r = httpx.get(base + "/api/v0/models", timeout=timeout)
                r.raise_for_status()
                modelli = [{"id": m["id"], "nome": m["id"], "caricato": m.get("state") == "loaded",
                            "tipo": m.get("type"), "quantizzazione": m.get("quantization"),
                            "architettura": m.get("arch"), "contesto": m.get("max_context_length")}
                           for m in r.json().get("data", []) if m.get("type") != "embeddings" and not ESCLUDI_CHAT.search(m["id"])]
            except httpx.HTTPStatusError:
                r = httpx.get(_base("lmstudio") + "/models", timeout=timeout)
                r.raise_for_status()
                modelli = [{"id": m["id"], "nome": m["id"]} for m in r.json().get("data", []) if not ESCLUDI_CHAT.search(m["id"])]
            return {"acceso": True, "modelli": modelli}
        # OpenRouter: l'elenco è pubblico, la chiave serve solo per rispondere
        r = httpx.get(_base("openrouter") + "/models", timeout=timeout + 6)
        r.raise_for_status()
        modelli = []
        for m in r.json().get("data", []):
            prezzo = m.get("pricing") or {}
            modelli.append({"id": m["id"], "nome": m.get("name") or m["id"], "contesto": m.get("context_length"),
                            "gratis": str(prezzo.get("prompt")) == "0" and str(prezzo.get("completion")) == "0"})
        modelli.sort(key=lambda m: m["id"])
        return {"acceso": True, "modelli": modelli, "chiave": bool(config.chiave_openrouter())}
    except Exception as e:
        return {"acceso": False, "errore": _errore_leggibile(fornitore, e), "modelli": []}


def _errore_leggibile(fornitore, e) -> str:
    if isinstance(e, httpx.ConnectError):
        return {"ollama": "Ollama non è acceso (apri l'app Ollama).",
                "lmstudio": "LM Studio non risponde: apri LM Studio e attiva il server (Developer → Start Server).",
                "openrouter": "Nessuna connessione a internet verso OpenRouter."}[fornitore]
    if isinstance(e, httpx.TimeoutException):
        return "Il server non ha risposto in tempo."
    return str(e)[:200]


def conversa(fornitore: str, modello: str, messaggi: list[dict], temperatura: float = 0.1, max_token: int = 8000,
             ragionamento: bool = True):
    """Genera eventi: ('ragionamento', testo) · ('testo', testo) · ('fine', statistiche).

    Gestisce sia il ragionamento in un campo separato (LM Studio, Ollama, OpenRouter)
    sia i modelli che lo scrivono dentro <think>...</think>.
    """
    if fornitore == "openrouter" and not config.chiave_openrouter():
        raise RuntimeError("Manca la chiave OpenRouter: imposta OPENROUTER_API_KEY e riavvia l'app.")
    corpo = {"model": modello, "messages": messaggi, "temperature": temperatura, "max_tokens": max_token,
             "stream": True, "stream_options": {"include_usage": True}}
    if not ragionamento:
        # i modelli "pensanti" rispondono subito, ma di solito con meno precisione
        corpo["reasoning_effort"] = "none"
    inizio = time.perf_counter()
    primo = None
    uso = None
    dentro_think = False
    buffer = ""
    caratteri = 0
    motivo = None
    try:
        with httpx.stream("POST", _base(fornitore) + "/chat/completions", json=corpo,
                          headers=_intestazioni(fornitore), timeout=httpx.Timeout(600, connect=10)) as r:
            if r.status_code >= 400:
                r.read()
                raise RuntimeError(f"{config.FORNITORI[fornitore]['nome']} ha risposto {r.status_code}: {r.text[:300]}")
            for riga in r.iter_lines():
                if not riga.startswith("data:"):
                    continue
                dato = riga[5:].strip()
                if dato == "[DONE]":
                    break
                try:
                    j = json.loads(dato)
                except json.JSONDecodeError:
                    continue
                if j.get("error"):
                    raise RuntimeError(str(j["error"].get("message") if isinstance(j["error"], dict) else j["error"]))
                if j.get("usage"):
                    uso = j["usage"]
                for scelta in j.get("choices") or []:
                    if scelta.get("finish_reason"):
                        motivo = scelta["finish_reason"]
                    delta = scelta.get("delta") or {}
                    ragion = delta.get("reasoning_content") or delta.get("reasoning")
                    if ragion:
                        primo = primo or time.perf_counter()
                        yield ("ragionamento", ragion)
                    testo = delta.get("content")
                    if not testo:
                        continue
                    primo = primo or time.perf_counter()
                    buffer += testo
                    # separa <think>...</think> dal testo vero
                    while buffer:
                        if dentro_think:
                            i = buffer.find("</think>")
                            if i == -1:
                                if len(buffer) > 8:
                                    yield ("ragionamento", buffer[:-8])
                                    buffer = buffer[-8:]
                                break
                            yield ("ragionamento", buffer[:i])
                            buffer = buffer[i + 8:]
                            dentro_think = False
                        else:
                            i = buffer.find("<think>")
                            if i == -1:
                                tieni = 6 if "<" in buffer[-6:] else 0
                                uscita = buffer[:len(buffer) - tieni] if tieni else buffer
                                if uscita:
                                    caratteri += len(uscita)
                                    yield ("testo", uscita)
                                buffer = buffer[len(uscita):]
                                break
                            if i:
                                caratteri += i
                                yield ("testo", buffer[:i])
                            buffer = buffer[i + 7:]
                            dentro_think = True
        if buffer:
            yield ("ragionamento" if dentro_think else "testo", buffer)
    except httpx.ConnectError:
        raise RuntimeError(_errore_leggibile(fornitore, httpx.ConnectError("")))
    fine = time.perf_counter()
    token = (uso or {}).get("completion_tokens")
    yield ("fine", {
        "secondi": round(fine - inizio, 2),
        "primo_token": round((primo or fine) - inizio, 2),
        "token": token,
        "token_al_secondo": round(token / max(fine - (primo or inizio), 1e-3), 1) if token else None,
        "token_domanda": (uso or {}).get("prompt_tokens"),
        "troncata": motivo == "length",
        "vuota": caratteri == 0,
    })


def scalda(fornitore: str, modello: str) -> dict:
    """Carica il modello in memoria prima della prima domanda (in aula non si aspetta)."""
    t = time.perf_counter()
    try:
        if fornitore == "ollama":
            httpx.post(_base("ollama").removesuffix("/v1") + "/api/generate",
                       json={"model": modello, "keep_alive": "30m"}, timeout=300).raise_for_status()
        elif fornitore == "lmstudio":
            httpx.post(_base("lmstudio") + "/chat/completions", timeout=300, json={
                "model": modello, "messages": [{"role": "user", "content": "ok"}], "max_tokens": 1}).raise_for_status()
        else:
            return {"ok": True, "secondi": 0}
        return {"ok": True, "secondi": round(time.perf_counter() - t, 1)}
    except Exception as e:
        return {"ok": False, "errore": _errore_leggibile(fornitore, e)}


def libera(fornitore: str, modello: str) -> None:
    """Toglie il modello dalla memoria (il banco prova ne carica tanti, uno dopo l'altro)."""
    import shutil
    import subprocess
    from pathlib import Path
    try:
        if fornitore == "ollama":
            httpx.post(_base("ollama").removesuffix("/v1") + "/api/generate",
                       json={"model": modello, "keep_alive": 0}, timeout=60)
        elif fornitore == "lmstudio":
            lms = shutil.which("lms") or str(Path.home() / ".lmstudio/bin/lms")
            if Path(lms).exists():
                subprocess.run([lms, "unload", modello], capture_output=True, timeout=60)
    except Exception:
        pass


def risposta_completa(fornitore, modello, messaggi, **kw) -> tuple[str, str, dict]:
    testo, ragion, stat = [], [], {}
    for tipo, dato in conversa(fornitore, modello, messaggi, **kw):
        if tipo == "testo":
            testo.append(dato)
        elif tipo == "ragionamento":
            ragion.append(dato)
        else:
            stat = dato
    return "".join(testo).strip(), "".join(ragion).strip(), stat
