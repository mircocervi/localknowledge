"""Il server web: pagina del cliente (/), area admin (/admin), API (/api/...) e server MCP (/mcp/...)."""
import asyncio
import contextlib
import json
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import VERSIONE, config, modelli, moduli, prova_finale, risposta, sistema, vettori
from .indice import Indice
from .indicizzatore import Indicizzatore
from .mcp_documenti import crea_mcp, crea_mcp_bi
from .servizio import Archivio

HOST_AMMESSI = {"127.0.0.1", "localhost", "[::1]"}


class Guardia:
    """Protezione di un'app locale: niente richieste con Host estranei (DNS rebinding) e niente
    modifiche richieste da altri siti aperti nel browser (CSRF)."""

    def __init__(self, app, porta_ok=None):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            h = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            host = h.get("host", "").rsplit(":", 1)[0] if not h.get("host", "").startswith("[") else h["host"].split("]")[0] + "]"
            origine = h.get("origin")
            vietato = host not in HOST_AMMESSI
            if not vietato and origine and scope["method"] not in ("GET", "HEAD", "OPTIONS"):
                o = origine.split("//", 1)[-1].rsplit(":", 1)[0]
                vietato = o not in HOST_AMMESSI
            if vietato:
                await send({"type": "http.response.start", "status": 403,
                            "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
                await send({"type": "http.response.body", "body": "Archivio risponde solo da questo computer.".encode()})
                return
        await self.app(scope, receive, send)


class Smistatore:
    """Manda /mcp/documenti e /mcp/bi ai server MCP, tutto il resto a FastAPI."""

    def __init__(self, principale, mcp_app: dict):
        self.principale, self.mcp_app = principale, mcp_app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            percorso = scope["path"].rstrip("/")
            for prefisso, (app, attivo) in self.mcp_app.items():
                if percorso == prefisso:
                    if not attivo():
                        await send({"type": "http.response.start", "status": 404,
                                    "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
                        await send({"type": "http.response.body", "body": "Modulo spento: accendilo da /admin → Moduli.".encode()})
                        return
                    scope = dict(scope, path=prefisso)
                    return await app(scope, receive, send)
        await self.principale(scope, receive, send)


def crea_app():
    indice = Indice()
    lavoratore = Indicizzatore(indice)
    archivio = Archivio(indice)
    mcp_doc = crea_mcp(archivio)
    mcp_bi = crea_mcp_bi()
    app_doc = mcp_doc.http_app(path="/mcp/documenti")
    app_bi = mcp_bi.http_app(path="/mcp/bi")
    prova = {"in_corso": False, "fatti": 0, "totale": 0, "attuale": None, "risultati": None, "ragionamento": False}

    @contextlib.asynccontextmanager
    async def vita(_app):
        async with app_doc.lifespan(app_doc), app_bi.lifespan(app_bi):
            lavoratore.scansiona_tutto()
            lavoratore.completa_vettori()
            yield

    app = FastAPI(title="Archivio", version=VERSIONE, lifespan=vita, docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=config.DIR_WEB), name="static")

    def pagina(nome):
        return FileResponse(config.DIR_WEB / nome, headers={"Cache-Control": "no-store"})

    @app.get("/", include_in_schema=False)
    def cliente():
        return pagina("cliente.html")

    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/{_resto:path}", include_in_schema=False)
    def admin(_resto: str = ""):
        return pagina("admin.html")

    # ---------------- stato ----------------

    def cartelle_con_stat():
        stat = indice.statistiche()
        out = []
        for c in config.leggi()["cartelle"]:
            s = stat["cartelle"].get(c["id"], {})
            out.append({**c, "esiste": Path(c["percorso"]).is_dir(), "documenti": s.get("documenti", 0),
                        "pagine": s.get("pagine", 0), "pagine_ocr": s.get("pagine_ocr", 0),
                        "pezzi": s.get("pezzi", 0), "errori": s.get("errori", 0) or 0})
        return out, stat["totale"]

    @app.get("/api/stato")
    def stato(dopo: float = 0):
        imp = config.leggi()
        cartelle, totale = cartelle_con_stat()
        return {
            "versione": VERSIONE,
            "cartelle": cartelle,
            "totale": totale,
            "indicizzazione": {**lavoratore.stato, "in_coda": lavoratore.coda.qsize()},
            "registro": [r for r in list(lavoratore.registro) if r["t"] > dopo][-200:],
            "ora": time.time(),
            "scelta": {"fornitore": imp["fornitore"], "modello": imp["modello"], "ragionamento": imp.get("ragionamento", True),
                       "modo": imp.get("modo", "auto")},
            "fornitori": {k: {"nome": v["nome"], "locale": v["locale"], "url": v["url"]} for k, v in config.FORNITORI.items()},
            "openrouter_chiave": bool(config.chiave_openrouter()),
            "preferiti": imp.get("preferiti", {}),
            "moduli": moduli.elenco(),
            "domande_esempio": imp["domande_esempio"],
        }

    @app.get("/api/modelli/{fornitore}")
    def elenco_modelli(fornitore: str):
        if fornitore not in config.FORNITORI:
            raise HTTPException(404, "fornitore sconosciuto")
        return modelli.elenco(fornitore)

    @app.get("/api/modelli")
    def tutti_i_modelli():
        with ThreadPoolExecutor(3) as ex:
            ris = dict(zip(config.FORNITORI, ex.map(modelli.elenco, config.FORNITORI)))
        return ris

    @app.post("/api/scelta")
    async def scegli(req: Request):
        d = await req.json()
        campi = {}
        if d.get("fornitore") in config.FORNITORI:
            campi["fornitore"] = d["fornitore"]
        if isinstance(d.get("modello"), str):
            campi["modello"] = d["modello"]
            f = campi.get("fornitore") or config.leggi()["fornitore"]
            campi["preferiti"] = {f: d["modello"]}
        if "ragionamento" in d:
            campi["ragionamento"] = bool(d["ragionamento"])
        if d.get("modo") in ("auto", "tutto", "ricerca"):
            campi["modo"] = d["modo"]
        return config.aggiorna(**campi) and {"ok": True}

    @app.post("/api/ferma")
    def ferma():
        """Ferma le risposte in corso (e il banco prova tra una domanda e l'altra)."""
        prova_finale.FERMA["si"] = True
        return {"fermate": modelli.ferma_tutto()}

    @app.post("/api/motore/spegni")
    async def spegni_motore():
        """Ferma tutto e toglie i modelli dalla memoria: il Mac si raffredda."""
        prova_finale.FERMA["si"] = True
        n = modelli.ferma_tutto()
        r = await asyncio.to_thread(modelli.libera_tutto)
        lavoratore.log(f"Motore spento: fermate {n} risposte, tolti dalla memoria {len(r['tolti'])} modelli.", "avviso")
        return {"fermate": n, **r}

    @app.get("/api/motore")
    async def stato_motore():
        return {"in_memoria": await asyncio.to_thread(modelli.in_memoria),
                "risposte_in_corso": len(modelli._freni), "prova_in_corso": prova["in_corso"]}

    @app.post("/api/scalda")
    async def scalda(req: Request):
        d = await req.json()
        imp = config.leggi()
        f, m = d.get("fornitore") or imp["fornitore"], d.get("modello") or imp["modello"]
        if f not in config.FORNITORI or not m:
            raise HTTPException(400, "modello sconosciuto")
        return await asyncio.to_thread(modelli.scalda, f, m)

    # ---------------- cartelle ----------------

    @app.post("/api/cartelle/scegli")
    def scegli_cartella():
        """Apre il selettore di cartelle di macOS (l'app gira su questo Mac)."""
        script = 'POSIX path of (choose folder with prompt "Scegli la cartella dei documenti da interrogare")'
        try:
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=300)
        except Exception as e:
            raise HTTPException(500, f"Selettore non disponibile: {e}")
        if r.returncode != 0:
            return {"annullato": True}
        return {"percorso": r.stdout.strip().rstrip("/")}

    @app.post("/api/cartelle")
    async def aggiungi_cartella(req: Request):
        d = await req.json()
        percorso = Path(str(d.get("percorso", "")).strip()).expanduser()
        if not percorso.is_absolute() or not percorso.is_dir():
            raise HTTPException(400, "Cartella non trovata: scrivi il percorso completo, per esempio /Users/nome/Documenti/data-room")
        percorso = percorso.resolve()
        if percorso == Path("/") or percorso == Path.home():
            raise HTTPException(400, "Scegli una cartella di documenti, non l'intero disco o la cartella Inizio.")
        if config.DIR_INDICE.resolve() in (percorso, *percorso.parents) or percorso in config.DIR_INDICE.resolve().parents:
            raise HTTPException(400, "Non posso indicizzare la cartella dell'indice o una che la contiene.")
        imp = config.leggi()
        if any(Path(c["percorso"]) == percorso for c in imp["cartelle"]):
            raise HTTPException(409, "Questa cartella c'è già.")
        nuova = {"id": config.nuovo_id(), "nome": (d.get("nome") or percorso.name).strip()[:80],
                 "percorso": str(percorso), "attiva": True, "aggiunta_il": time.time()}
        config.aggiorna(cartelle=imp["cartelle"] + [nuova])
        lavoratore.log(f"Aggiunta la cartella «{nuova['nome']}» ({percorso}).")
        lavoratore.scansiona(nuova["id"])
        return nuova

    @app.patch("/api/cartelle/{cid}")
    async def modifica_cartella(cid: str, req: Request):
        d = await req.json()
        imp = config.leggi()
        for c in imp["cartelle"]:
            if c["id"] == cid:
                if "attiva" in d:
                    c["attiva"] = bool(d["attiva"])
                if d.get("nome"):
                    c["nome"] = str(d["nome"]).strip()[:80]
                config.aggiorna(cartelle=imp["cartelle"])
                return c
        raise HTTPException(404, "cartella sconosciuta")

    @app.delete("/api/cartelle/{cid}")
    def togli_cartella(cid: str):
        imp = config.leggi()
        c = next((c for c in imp["cartelle"] if c["id"] == cid), None)
        if not c:
            raise HTTPException(404, "cartella sconosciuta")
        lavoratore.smetti_di_osservare(cid)
        indice.rimuovi_cartella(cid)
        config.aggiorna(cartelle=[x for x in imp["cartelle"] if x["id"] != cid])
        lavoratore.log(f"Tolta la cartella «{c['nome']}» dall'archivio. I file originali non sono stati toccati.")
        return {"ok": True}

    @app.post("/api/cartelle/{cid}/reindicizza")
    def reindicizza_cartella(cid: str, forza: bool = True):
        lavoratore.scansiona(cid, forza)
        return {"ok": True}

    @app.post("/api/vettori/completa")
    def completa_vettori():
        lavoratore.completa_vettori()
        return {"ok": True}

    # ---------------- documenti ----------------

    @app.get("/api/documenti")
    def documenti(cartella: str | None = None):
        return indice.documenti(cartella)

    @app.get("/api/documenti/{doc_id}")
    def documento(doc_id: int):
        d = indice.documento_da_id(doc_id)
        if not d:
            raise HTTPException(404, "documento sconosciuto")
        return {"documento": d, "pagine": indice.pagine_di(doc_id), "pezzi": indice.pezzi_di(doc_id)}

    @app.post("/api/documenti/{doc_id}/reindicizza")
    def reindicizza_documento(doc_id: int):
        d = indice.documento_da_id(doc_id)
        if not d:
            raise HTTPException(404, "documento sconosciuto")
        lavoratore.reindicizza_documento(d["cartella_id"], d["relpath"])
        return {"ok": True}

    def _file_documento(doc_id):
        d = indice.documento_da_id(doc_id)
        c = d and next((c for c in config.leggi()["cartelle"] if c["id"] == d["cartella_id"]), None)
        if not c:
            raise HTTPException(404, "documento sconosciuto")
        radice = Path(c["percorso"]).resolve()
        p = (radice / d["relpath"]).resolve()
        if radice not in p.parents or not p.is_file():
            raise HTTPException(404, "file non trovato")
        return d, p

    @app.get("/documento/{doc_id}")
    def apri_documento(doc_id: int):
        """L'originale, in sola lettura. I PDF si aprono alla pagina giusta con #page=N."""
        d, p = _file_documento(doc_id)
        tipi = {"pdf": "application/pdf", "txt": "text/plain; charset=utf-8", "md": "text/plain; charset=utf-8",
                "markdown": "text/plain; charset=utf-8", "csv": "text/plain; charset=utf-8"}
        if d["estensione"] not in tipi:
            return HTMLResponse(status_code=307, headers={"Location": f"/documento/{doc_id}/testo"})
        return FileResponse(p, media_type=tipi[d["estensione"]],
                            headers={"Content-Disposition": f"inline; filename*=UTF-8''{_q(d['nome'])}"})

    @app.get("/documento/{doc_id}/testo")
    def testo_documento(doc_id: int):
        return pagina("documento.html")

    # ---------------- domande ----------------

    def _sse(evento, dati):
        return f"event: {evento}\ndata: {json.dumps(dati, ensure_ascii=False)}\n\n"

    @app.post("/api/chiedi")
    async def chiedi(req: Request):
        d = await req.json()
        domanda = str(d.get("domanda", "")).strip()[:2000]
        if not domanda:
            raise HTTPException(400, "Scrivi una domanda.")
        imp = config.leggi()
        fornitore = d.get("fornitore") or imp["fornitore"]
        modello = d.get("modello") or imp["modello"]
        ragionamento = bool(d.get("ragionamento", imp.get("ragionamento", True)))
        modo = d.get("modo") if d.get("modo") in ("auto", "tutto", "ricerca") else imp.get("modo", "auto")
        cartelle = d.get("cartelle")
        if fornitore not in config.FORNITORI:
            raise HTTPException(400, "fornitore sconosciuto")

        def flusso():
            yield _sse("fase", {"t": "Preparo il modello e i documenti"})
            try:
                r = archivio.prepara(domanda, fornitore, modello, cartelle, modo, ragionamento)
            except Exception as e:
                yield _sse("errore", {"messaggio": f"Preparazione non riuscita: {e}"})
                return
            for tentativo in range(2):
                estratti = r["estratti"]
                yield _sse("estratti", {
                    "estratti": [e.dict() for e in estratti], "versioni": r["versioni"], "tempi": r["tempi"],
                    "avviso": r["avviso"], "fornitore": fornitore, "modello": modello, "modo": r["modo"],
                    "contesto": r.get("contesto"), "token_documenti": r.get("token_documenti"),
                    "documenti": r.get("documenti"), "locale": config.FORNITORI[fornitore]["locale"]})
                if not estratti:
                    testo = risposta.NON_PRESENTE
                    yield _sse("testo", {"t": testo})
                    yield _sse("fine", {"statistiche": {"secondi": 0, "primo_token": 0, "nessun_estratto": True},
                                        "verifica": risposta.verifica(testo, [])})
                    return
                parti = []
                try:
                    for tipo, dato in modelli.conversa(fornitore, modello, archivio.messaggi(domanda, r),
                                                       ragionamento=ragionamento, contesto_token=r.get("contesto")):
                        if tipo == "testo":
                            parti.append(dato)
                            yield _sse("testo", {"t": dato})
                        elif tipo == "ragionamento":
                            yield _sse("ragionamento", {"t": dato})
                        else:
                            testo = "".join(parti).strip()
                            yield _sse("fine", {"statistiche": dato, "verifica": risposta.verifica(testo, estratti)})
                    return
                except Exception as e:
                    troppo = re.search(r"context|contesto|exceed", str(e), re.I)
                    if tentativo == 0 and troppo and not parti:
                        # il modello ha meno contesto del previsto: si riprova con la ricerca e meno pagine
                        yield _sse("fase", {"t": "Il contesto del modello è più piccolo del previsto: riprovo con la ricerca"})
                        modelli._contesti[(fornitore, modello)] = (max(2048, (r.get("contesto") or 4096) // 2), time.time())
                        r = archivio.prepara(domanda, fornitore, modello, cartelle, "ricerca", ragionamento)
                        continue
                    yield _sse("errore", {"messaggio": str(e)})
                    return

        return StreamingResponse(flusso(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    # ---------------- laboratorio (admin) ----------------

    @app.post("/api/laboratorio/cerca")
    async def laboratorio(req: Request):
        d = await req.json()
        domanda = str(d.get("domanda", "")).strip()
        if not domanda:
            raise HTTPException(400, "Scrivi una domanda.")
        from .indice import domanda_fts
        r = await asyncio.to_thread(archivio.cerca, domanda, None, 10)
        ids = {pid for lista in r["classifiche"].values() for pid, _ in lista[:10]}
        dati = indice.risultati(list(ids))

        def lista(nome):
            return [{"pezzo_id": pid, "punteggio": round(s, 4), "nome": dati[pid].nome, "pagina": dati[pid].pagina,
                     "doc_id": dati[pid].doc_id, "testo": dati[pid].testo[:220]}
                    for pid, s in r["classifiche"][nome][:10] if pid in dati]

        return {"query_parole": domanda_fts(domanda, config.leggi().get("sinonimi")),
                "parole": lista("parole"), "significato": lista("significato"),
                "fusa": [e.dict() for e in r["estratti"]], "versioni": r["versioni"], "tempi": r["tempi"],
                "messaggi": archivio.messaggi(domanda, r)}

    @app.post("/api/laboratorio/vettori")
    async def laboratorio_vettori(req: Request):
        d = await req.json()
        frasi = [str(f).strip()[:500] for f in d.get("frasi", []) if str(f).strip()][:6]
        if len(frasi) < 2:
            raise HTTPException(400, "Servono almeno due frasi.")
        try:
            v = await asyncio.to_thread(vettori.calcola, frasi)
        except vettori.VettoriNonDisponibili as e:
            raise HTTPException(503, str(e))
        sim = (v @ v.T).round(3).tolist()
        return {"frasi": frasi, "dimensioni": int(v.shape[1]), "anteprima": [x[:16].round(3).tolist() for x in v],
                "similarita": sim, "modello": config.leggi()["embedding"]["modello"]}

    @app.get("/api/rag/numeri")
    async def numeri_rag():
        """I numeri veri dell'archivio per la lezione sul RAG."""
        imp = config.leggi()
        cartelle = archivio.cartelle_attive()
        pagine = await asyncio.to_thread(archivio._pagine_tutte, cartelle)
        caratteri = sum(len(p.testo) for p in pagine)
        stat = indice.statistiche()["totale"]
        ctx = await asyncio.to_thread(modelli.contesto, imp["fornitore"], imp["modello"])
        noti = {f"{f} · {m}": c for (f, m), (c, _) in modelli._contesti.items() if c}
        esempio = next((d for d in indice.documenti() if "Rinnovo_Nordwand_2024" in d["nome"]), None) \
            or next(iter(indice.documenti()), None)
        return {"caratteri": caratteri, "token": sum(modelli.stima_token(p.testo) for p in pagine),
                "pagine": len(pagine), "documenti": len({p.doc_id for p in pagine}), "pezzi": stat["pezzi"],
                "dimensioni": stat["dimensioni_vettore"], "modello": imp["modello"], "fornitore": imp["fornitore"],
                "contesto": ctx, "contesti_noti": noti, "esempio_doc": esempio and esempio["id"],
                "pezzo": imp["pezzi"], "estratti": imp["ricerca"]["estratti"], "embedding": imp["embedding"]["modello"]}

    # ---------------- sistema, impostazioni, mcp, moduli ----------------

    @app.get("/api/sistema")
    def stato_sistema():
        return sistema.componenti()

    @app.get("/api/impostazioni")
    def leggi_impostazioni():
        return config.leggi()

    @app.post("/api/impostazioni")
    async def scrivi_impostazioni(req: Request):
        d = await req.json()
        ammessi = {"ocr", "ricerca", "pezzi", "sinonimi", "domande_esempio", "mcp_esterni"}
        campi = {k: v for k, v in d.items() if k in ammessi}
        if "ricerca" in campi:
            ric = campi["ricerca"]
            campi["ricerca"] = {"estratti": max(1, min(int(ric.get("estratti", 8)), 30)),
                                "candidati": max(10, min(int(ric.get("candidati", 40)), 200)),
                                "limite_tutto": max(2000, min(int(ric.get("limite_tutto", 60000)), 900000)),
                                "limite_ricerca": max(1500, min(int(ric.get("limite_ricerca", 14000)), 200000))}
        if "pezzi" in campi:
            campi["pezzi"] = {"dimensione": max(300, min(int(campi["pezzi"].get("dimensione", 1000)), 4000)),
                              "sovrapposizione": max(0, min(int(campi["pezzi"].get("sovrapposizione", 150)), 1000))}
        if "sinonimi" in campi:
            campi["sinonimi"] = [str(s).strip() for s in campi["sinonimi"] if str(s).strip()][:200]
        if "domande_esempio" in campi:
            campi["domande_esempio"] = [str(s).strip() for s in campi["domande_esempio"] if str(s).strip()][:12]
        if "mcp_esterni" in campi:
            campi["mcp_esterni"] = [
                {"id": m.get("id") or config.nuovo_id(), "nome": str(m.get("nome", ""))[:80], "url": str(m.get("url", ""))[:300],
                 "descrizione": str(m.get("descrizione", ""))[:300], "avvio": str(m.get("avvio", ""))[:300]}
                for m in campi["mcp_esterni"] if str(m.get("url", "")).startswith(("http://127.0.0.1", "http://localhost"))]
        config.aggiorna(**campi)
        return config.leggi()

    @app.get("/api/mcp")
    async def stato_dei_mcp():
        imp = config.leggi()
        propri = [
            {"id": "documenti", "nome": "Documenti (questa app)", "url": "http://127.0.0.1:4100/mcp/documenti",
             "descrizione": "Ricerca ibrida nei documenti indicizzati, con documento e pagina.", "proprio": True,
             "avvio": "acceso insieme all'app"},
            {"id": "documenti-solo", "nome": "Documenti (server autonomo)", "url": "http://127.0.0.1:4101/mcp",
             "descrizione": "Lo stesso MCP senza l'app: gemello del server di Crinale.", "proprio": True,
             "avvio": "uv run server_mcp_documenti.py"},
            {"id": "bi", "nome": "BI (modulo)", "url": "http://127.0.0.1:4100/mcp/bi", "proprio": True,
             "descrizione": "Segnaposto del modulo BI: si accende da Moduli.", "modulo": "bi",
             "avvio": "si accende da Moduli"},
        ]
        tutti = propri + [{**m, "proprio": False} for m in imp["mcp_esterni"]]
        stati = await asyncio.gather(*[asyncio.to_thread(sistema.stato_mcp, m["url"]) for m in tutti])
        return [{**m, **s} for m, s in zip(tutti, stati)]

    @app.post("/api/mcp/prova")
    async def prova_mcp(req: Request):
        """Chiama uno strumento del nostro MCP, come farebbe Unsloth Studio."""
        from fastmcp import Client
        d = await req.json()
        try:
            async with Client(mcp_doc) as c:
                r = await c.call_tool(d.get("strumento", "descrivi_archivio"), d.get("argomenti") or {})
            testo = "\n".join(getattr(b, "text", "") for b in r.content)
            return {"testo": testo}
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/moduli/{mid}")
    async def accendi_modulo(mid: str, req: Request):
        if mid not in moduli.MODULI:
            raise HTTPException(404, "modulo sconosciuto")
        d = await req.json()
        config.aggiorna(moduli={mid: bool(d.get("acceso"))})
        lavoratore.log(f"Modulo {moduli.MODULI[mid]['nome']} {'acceso' if d.get('acceso') else 'spento'}.")
        return moduli.elenco()

    # ---------------- banco prova ----------------

    @app.get("/api/prova")
    def stato_prova():
        return {**prova, "prove": [{k: v for k, v in p.items() if k != "contenuto"} for p in prova_finale.PROVE],
                "ultima": prova["risultati"] is None and prova_finale.ultima() or None}

    @app.post("/api/prova")
    async def avvia_prova(req: Request):
        if prova["in_corso"]:
            raise HTTPException(409, "C'è già una prova in corso.")
        d = await req.json()
        bersagli = [b for b in d.get("modelli", []) if b.get("fornitore") in config.FORNITORI and b.get("modello")]
        if not bersagli:
            raise HTTPException(400, "Scegli almeno un modello.")
        prova.update(in_corso=True, fatti=0, totale=len(bersagli) * len(prova_finale.PROVE), risultati=[],
                     ragionamento=bool(d.get("ragionamento")), attuale=None,
                     modo=d.get("modo") if d.get("modo") in ("auto", "tutto", "ricerca") else "auto")

        def avanti(i, n, b, p):
            prova.update(fatti=i, totale=n, attuale=b and {**b, "prova": p["id"]})

        def lavora():
            try:
                prova["risultati"] = prova_finale.esegui(archivio, bersagli, prova["ragionamento"], avanti, prova["modo"])
            except Exception as e:
                lavoratore.log(f"Banco prova interrotto: {e}", "errore")
            finally:
                prova.update(in_corso=False, attuale=None)

        threading.Thread(target=lavora, daemon=True).start()
        return {"ok": True}

    mcp_attivi = {
        "/mcp/documenti": (app_doc, lambda: True),
        "/mcp/bi": (app_bi, lambda: moduli.acceso("bi")),
    }
    return Guardia(Smistatore(app, mcp_attivi))


def _q(s: str) -> str:
    from urllib.parse import quote
    return quote(s)
