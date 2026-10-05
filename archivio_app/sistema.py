"""Cosa c'è installato e a cosa serve: la "scheda per l'aula" di /admin, verificata dal vivo."""
import importlib.metadata as md
import platform
import shutil
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import httpx

from . import VERSIONE, config, modelli

LIBRERIE = [
    ("fastapi", "Il server web dell'app (le pagine e le API)", "MIT"),
    ("uvicorn", "Il motore che fa girare il server su 127.0.0.1", "BSD-3"),
    ("fastmcp", "Il server MCP, lo stesso del server Crinale", "Apache-2.0"),
    ("httpx", "Le chiamate a Ollama, LM Studio e OpenRouter", "BSD-3"),
    ("numpy", "La matrice dei vettori e la ricerca per significato", "BSD-3"),
    ("pypdfium2", "Legge i PDF pagina per pagina (motore PDFium di Chrome)", "Apache-2.0 / BSD-3"),
    ("pillow", "Trasforma le pagine scansionate in immagini per l'OCR", "MIT-CMU"),
    ("python-docx", "Legge i file Word .docx", "MIT"),
    ("watchdog", "Si accorge quando aggiungi o cambi un file nella cartella", "Apache-2.0"),
]


def _cmd(args, timeout=4) -> str | None:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or r.stderr).strip()
    except Exception:
        return None


def _mac() -> dict:
    chip = _cmd(["sysctl", "-n", "machdep.cpu.brand_string"]) or platform.processor()
    ram = _cmd(["sysctl", "-n", "hw.memsize"])
    return {"chip": chip, "ram_gb": round(int(ram) / 2**30) if ram and ram.isdigit() else None,
            "sistema": f"macOS {platform.mac_ver()[0]}" if platform.mac_ver()[0] else platform.platform()}


def _ollama() -> dict:
    base = config.FORNITORI["ollama"]["url"].removesuffix("/v1")
    try:
        ver = httpx.get(base + "/api/version", timeout=2).json().get("version")
        tags = httpx.get(base + "/api/tags", timeout=3).json().get("models", [])
        ps = {m["name"] for m in httpx.get(base + "/api/ps", timeout=3).json().get("models", [])}
        return {"acceso": True, "versione": ver, "modelli": [
            {"nome": m["name"], "gb": round(m.get("size", 0) / 1e9, 1), "in_memoria": m["name"] in ps,
             "parametri": (m.get("details") or {}).get("parameter_size"),
             "embedding": bool(modelli.ESCLUDI_CHAT.search(m["name"]))} for m in tags]}
    except Exception:
        return {"acceso": False, "installato": bool(shutil.which("ollama")), "modelli": []}


def _lmstudio() -> dict:
    base = config.FORNITORI["lmstudio"]["url"].removesuffix("/v1")
    try:
        dati = httpx.get(base + "/api/v0/models", timeout=3).json().get("data", [])
        return {"acceso": True, "modelli": [
            {"nome": m["id"], "tipo": m.get("type"), "caricato": m.get("state") == "loaded",
             "quantizzazione": m.get("quantization"), "contesto": m.get("max_context_length")} for m in dati]}
    except Exception:
        return {"acceso": False, "modelli": []}


def _tesseract() -> dict:
    if not shutil.which("tesseract"):
        return {"installato": False}
    ver = (_cmd(["tesseract", "--version"]) or "").splitlines()
    lingue = (_cmd(["tesseract", "--list-langs"]) or "").splitlines()[1:]
    return {"installato": True, "versione": ver[0].replace("tesseract ", "") if ver else "?",
            "italiano": "ita" in lingue, "lingue": len(lingue)}


def stato_mcp(url: str, timeout=3) -> dict:
    """Prova a 'stringere la mano' a un server MCP (initialize) e ne elenca gli strumenti."""
    intest = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    corpo = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "archivio-admin", "version": VERSIONE}}}
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(url, json=corpo, headers=intest)
            if r.status_code >= 400:
                return {"acceso": False, "errore": f"HTTP {r.status_code}"}
            info = _jsonrpc(r)
            sessione = r.headers.get("mcp-session-id")
            h2 = {**intest, **({"mcp-session-id": sessione} if sessione else {})}
            c.post(url, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=h2)
            t = c.post(url, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=h2)
            strumenti = [x["name"] for x in (_jsonrpc(t).get("result") or {}).get("tools", [])]
            srv = (info.get("result") or {}).get("serverInfo") or {}
            return {"acceso": True, "nome": srv.get("name"), "strumenti": strumenti}
    except httpx.ConnectError:
        return {"acceso": False, "errore": "spento"}
    except Exception as e:
        return {"acceso": False, "errore": str(e)[:120]}


def _jsonrpc(r) -> dict:
    import json
    if "text/event-stream" in r.headers.get("content-type", ""):
        for riga in r.text.splitlines():
            if riga.startswith("data:"):
                return json.loads(riga[5:])
        return {}
    return r.json() if r.content else {}


def componenti() -> dict:
    with ThreadPoolExecutor(4) as ex:
        f_oll, f_lms, f_tes, f_mac = ex.submit(_ollama), ex.submit(_lmstudio), ex.submit(_tesseract), ex.submit(_mac)
        oll, lms, tes, mac = f_oll.result(), f_lms.result(), f_tes.result(), f_mac.result()
    imp = config.leggi()
    emb = imp["embedding"]["modello"]
    emb_ok = any(m["nome"] in (emb, emb + ":latest") for m in oll.get("modelli", []))
    librerie = []
    for nome, ruolo, licenza in LIBRERIE:
        try:
            v = md.version(nome)
        except md.PackageNotFoundError:
            v = None
        librerie.append({"nome": nome, "versione": v, "ruolo": ruolo, "licenza": licenza})
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        fts5 = True
    except sqlite3.OperationalError:
        fts5 = False
    return {
        "app": {"versione": VERSIONE, "url": "http://127.0.0.1:4100", "admin": "http://127.0.0.1:4100/admin",
                "mcp": "http://127.0.0.1:4100/mcp/documenti", "indice": str(config.DIR_INDICE)},
        "mac": mac,
        "python": {"versione": platform.python_version(), "eseguibile": sys.executable,
                   "uv": ((_cmd(["uv", "--version"]) or "").replace("uv ", "").split(" ") or [None])[0] or None},
        "sqlite": {"versione": sqlite3.sqlite_version, "fts5": fts5},
        "ollama": oll,
        "lmstudio": lms,
        "openrouter": {"chiave": bool(config.chiave_openrouter())},
        "embedding": {"modello": emb, "presente": emb_ok, "dove": "Ollama, " + imp["embedding"]["url"]},
        "tesseract": tes,
        "ocr": imp["ocr"],
        "librerie": librerie,
    }
