"""I modelli che rispondono. Per tutti la stessa API compatibile OpenAI: cambia solo indirizzo e modello."""
import contextlib
import json
import re
import time

import httpx

from . import config

import threading

# Ogni risposta in corso ha il suo "freno". /api/ferma li tira tutti.
_freni: set = set()
_freni_lock = threading.Lock()


def ferma_tutto() -> int:
    with _freni_lock:
        for f in _freni:
            f.set()
        return len(_freni)


ESCLUDI_CHAT = re.compile(r"embed|embedding|rerank|bge-|nomic-bert|whisper", re.I)


CONTESTO_PIENO = re.compile(r"context (?:length|size|window)|maximum context|exceeds? the|too many tokens|contesto", re.I)


def e_contesto_pieno(errore: str) -> bool:
    """L'errore dice che il messaggio non entra nel contesto del modello? (non basta la parola 'context')"""
    return bool(CONTESTO_PIENO.search(errore))


def stima_token(testo: str) -> int:
    """Stima prudente: in italiano un token vale circa 3,3 caratteri."""
    return int(len(testo) / 3.3) + 1


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
             ragionamento: bool = True, contesto_token: int | None = None):
    """Genera eventi: ('ragionamento', testo) · ('testo', testo) · ('fine', statistiche).

    Gestisce sia il ragionamento in un campo separato (LM Studio, Ollama, OpenRouter)
    sia i modelli che lo scrivono dentro <think>...</think>.
    """
    if fornitore == "openrouter" and not config.chiave_openrouter():
        raise RuntimeError("Manca la chiave OpenRouter: imposta OPENROUTER_API_KEY e riavvia l'app.")
    if contesto_token:  # non chiedere più token di quanti ne restano nel contesto
        stima_domanda = stima_token("".join(m["content"] for m in messaggi))
        max_token = max(256, min(max_token, contesto_token - stima_domanda - 64))
    corpo = {"model": modello, "messages": messaggi, "temperature": temperatura, "max_tokens": max_token,
             "stream": True, "stream_options": {"include_usage": True}}
    if not ragionamento:
        # i modelli "pensanti" rispondono subito, ma di solito con meno precisione
        corpo["reasoning_effort"] = "none"
    freno = threading.Event()
    with _freni_lock:
        _freni.add(freno)
    fermata = False
    inizio = time.perf_counter()
    primo = None
    uso = None
    dentro_think = False
    buffer = ""
    caratteri = 0
    motivo = None
    try:
        cliente = httpx.Client(timeout=httpx.Timeout(600, connect=10))
        for tentativo in range(3):  # 429 = troppe richieste (piano gratuito): si aspetta e si riprova
            r = cliente.send(
                httpx.Request("POST", _base(fornitore) + "/chat/completions", json=corpo,
                              headers=_intestazioni(fornitore)), stream=True)
            if r.status_code == 429 and tentativo < 2 and not freno.is_set():
                r.close()
                time.sleep(6 * (tentativo + 1))
                continue
            break
        with contextlib.closing(cliente), contextlib.closing(r):
            if r.status_code == 429:
                r.read()
                raise RuntimeError(f"{config.FORNITORI[fornitore]['nome']}: troppe richieste (limite del piano gratuito). "
                                   "Aspetta un minuto o scegli un modello locale.")
            if r.status_code >= 400:
                r.read()
                raise RuntimeError(f"{config.FORNITORI[fornitore]['nome']} ha risposto {r.status_code}: {r.text[:300]}")
            for riga in r.iter_lines():
                if freno.is_set():  # chiudere la connessione ferma anche il modello
                    fermata = True
                    break
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
    finally:
        with _freni_lock:
            _freni.discard(freno)
    fine = time.perf_counter()
    token = (uso or {}).get("completion_tokens")
    yield ("fine", {
        "secondi": round(fine - inizio, 2),
        "primo_token": round((primo or fine) - inizio, 2),
        "token": token,
        "token_al_secondo": round(token / max(fine - (primo or inizio), 1e-3), 1) if token else None,
        "token_domanda": (uso or {}).get("prompt_tokens"),
        "troncata": motivo == "length",
        "interrotta": motivo is None and not fermata,  # il flusso si è chiuso senza dire perché
        "fermata": fermata,
        "vuota": caratteri == 0,
    })


CONTESTO_LMSTUDIO = 32768   # quanti token chiediamo a LM Studio quando carica un modello (se il modello li regge)
_contesti: dict = {}


def _lms() -> str | None:
    import shutil
    from pathlib import Path
    p = shutil.which("lms") or str(Path.home() / ".lmstudio/bin/lms")
    return p if Path(p).exists() else None


def _lms_json(*args, timeout=300):
    import subprocess
    lms = _lms()
    if not lms:
        return None
    r = subprocess.run([lms, *args, "--json"], capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def _contesto_lmstudio_caricato(modello: str) -> int | None:
    for m in _lms_json("ps", timeout=30) or []:
        if modello in (m.get("identifier"), m.get("modelKey"), m.get("path")):
            return m.get("contextLength")
    return None


def scalda(fornitore: str, modello: str) -> dict:
    """Carica il modello in memoria prima della prima domanda e dice quanto contesto ha davvero.

    Ollama sceglie da solo il contesto (o usa num_ctx del modello: MiniCPM5 in Ollama ha 4.096).
    LM Studio, se carica un modello "al volo", usa un contesto piccolo: qui lo carichiamo noi
    con CONTESTO_LMSTUDIO token, così l'archivio ci sta.
    """
    t = time.perf_counter()
    try:
        if fornitore == "ollama":
            base = _base("ollama").removesuffix("/v1")
            httpx.post(base + "/api/generate", json={"model": modello, "keep_alive": "30m"}, timeout=300).raise_for_status()
            ctx = next((m.get("context_length") for m in httpx.get(base + "/api/ps", timeout=5).json().get("models", [])
                        if m["name"] == modello), None)
        elif fornitore == "lmstudio":
            import subprocess
            ctx = _contesto_lmstudio_caricato(modello)
            if ctx is not None and ctx < 16384 and _lms():
                # caricato "al volo" con un contesto piccolo: lo ricarichiamo con quello ampio
                subprocess.run([_lms(), "unload", modello], capture_output=True, timeout=60)
                ctx = None
            if ctx is None and _lms():
                subprocess.run([_lms(), "server", "start"], capture_output=True, timeout=60)
                massimo = next((m.get("maxContextLength") for m in _lms_json("ls", timeout=30) or []
                                if m.get("modelKey") == modello), None) or CONTESTO_LMSTUDIO
                subprocess.run([_lms(), "load", modello, "-c", str(min(CONTESTO_LMSTUDIO, massimo)), "-y",
                                "--identifier", modello], capture_output=True, timeout=600)
                ctx = _contesto_lmstudio_caricato(modello)
            if ctx is None:  # senza la riga di comando: lo carica LM Studio al primo messaggio
                httpx.post(_base("lmstudio") + "/chat/completions", timeout=300, json={
                    "model": modello, "messages": [{"role": "user", "content": "ok"}], "max_tokens": 1}).raise_for_status()
                ctx = _contesto_lmstudio_caricato(modello) or 4096
        else:
            ctx = next((m.get("contesto") for m in elenco("openrouter").get("modelli", []) if m["id"] == modello), None) or 32768
        _contesti[(fornitore, modello)] = (ctx, time.time())
        return {"ok": True, "secondi": round(time.perf_counter() - t, 1), "contesto": ctx}
    except Exception as e:
        return {"ok": False, "errore": _errore_leggibile(fornitore, e)}


def contesto(fornitore: str, modello: str) -> int:
    """Token di contesto disponibili per questo modello (carica il modello se serve). Prudente se non si sa."""
    noto = _contesti.get((fornitore, modello))
    if noto and time.time() - noto[1] < 300 and noto[0]:
        return noto[0]
    r = scalda(fornitore, modello)
    return r.get("contesto") or 4096


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


def libera_tutto() -> dict:
    """Spegne il motore: toglie dalla memoria tutti i modelli di Ollama e LM Studio."""
    tolti = []
    try:
        base = _base("ollama").removesuffix("/v1")
        for m in httpx.get(base + "/api/ps", timeout=5).json().get("models", []):
            httpx.post(base + "/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=60)
            tolti.append("Ollama · " + m["name"])
    except Exception:
        pass
    for m in _lms_json("ps", timeout=30) or []:
        tolti.append("LM Studio · " + (m.get("identifier") or m.get("modelKey") or "?"))
    if _lms():
        import subprocess
        subprocess.run([_lms(), "unload", "--all"], capture_output=True, timeout=60)
    _contesti.clear()
    return {"tolti": tolti}


def in_memoria() -> list[str]:
    out = []
    try:
        base = _base("ollama").removesuffix("/v1")
        out += ["Ollama · " + m["name"] for m in httpx.get(base + "/api/ps", timeout=3).json().get("models", [])]
    except Exception:
        pass
    try:
        dati = httpx.get(_base("lmstudio").removesuffix("/v1") + "/api/v0/models", timeout=3).json().get("data", [])
        out += ["LM Studio · " + m["id"] for m in dati if m.get("state") == "loaded"]
    except Exception:
        pass
    return out


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
