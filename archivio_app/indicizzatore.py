"""Indicizzazione in sottofondo: una coda, un solo lavoratore, e un osservatore delle cartelle.

Quando un file cambia (aggiunto, modificato, cancellato) si reindicizza solo quello:
l'impronta SHA-256 dice se il contenuto è davvero cambiato.
"""
import hashlib
import os
import queue
import threading
import time
from collections import deque
from pathlib import Path

from . import config, estrazione, pezzi, vettori
from .indice import Indice


def impronta(percorso: Path) -> str:
    h = hashlib.sha256()
    with open(percorso, "rb") as f:
        for blocco in iter(lambda: f.read(1 << 20), b""):
            h.update(blocco)
    return h.hexdigest()


def da_ignorare(nome: str) -> bool:
    return nome.startswith((".", "~$", "._")) or nome.endswith((".tmp", ".part", ".crdownload"))


def elenca_file(cartella: Path):
    for radice, dirs, files in os.walk(cartella):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "indice"]
        for f in files:
            p = Path(radice) / f
            if p.suffix.lower() in config.ESTENSIONI and not da_ignorare(f):
                yield p


class Indicizzatore:
    def __init__(self, indice: Indice):
        self.indice = indice
        self.coda: queue.Queue = queue.Queue()
        self.registro: deque = deque(maxlen=400)
        self.stato = {"attivo": False, "cartella": None, "file": None, "fatti": 0, "totale": 0, "fase": "", "errore_vettori": None}
        self._osservatori = {}
        self._in_attesa: dict[str, float] = {}
        self._lock = threading.Lock()
        threading.Thread(target=self._lavora, daemon=True, name="indicizzatore").start()
        threading.Thread(target=self._smaltisci_eventi, daemon=True, name="eventi").start()

    # ---------- registro ----------

    def log(self, testo: str, livello: str = "info", evento: dict | None = None):
        """evento: {'tipo': 'nuovo'|'aggiornato'|'rimosso', 'nome': ...} per gli avvisi a comparsa del cliente."""
        self.registro.append({"t": time.time(), "testo": testo, "livello": livello, "evento": evento})

    # ---------- comandi ----------

    def scansiona(self, cartella_id: str, forza: bool = False):
        self.coda.put(("scansiona", cartella_id, forza))

    def scansiona_tutto(self, forza: bool = False):
        for c in config.leggi()["cartelle"]:
            self.scansiona(c["id"], forza)

    def reindicizza_documento(self, cartella_id: str, relpath: str):
        self.coda.put(("file", cartella_id, relpath, True))

    def completa_vettori(self):
        self.coda.put(("vettori",))

    # ---------- lavoratore ----------

    def _lavora(self):
        while True:
            lavoro = self.coda.get()
            try:
                self.stato["attivo"] = True
                if lavoro[0] == "scansiona":
                    self._scansiona(lavoro[1], lavoro[2])
                elif lavoro[0] == "file":
                    c = self._cartella(lavoro[1])
                    if c:
                        p = Path(c["percorso"]) / lavoro[2]
                        if p.exists():
                            self._indicizza(c, p, forza=lavoro[3])
                        else:
                            self.indice.rimuovi_documento(c["id"], lavoro[2])
                            self.log(f"Tolto dall'indice (non c'è più): {lavoro[2]}", "info",
                                     {"tipo": "rimosso", "nome": Path(lavoro[2]).name, "cartella": c["nome"]})
                elif lavoro[0] == "vettori":
                    self._completa_vettori()
            except Exception as e:  # il lavoratore non deve mai morire
                self.log(f"Errore: {e}", "errore")
            finally:
                if self.coda.empty():
                    self.stato.update(attivo=False, file=None, fase="", cartella=None)

    def _cartella(self, cartella_id):
        return next((c for c in config.leggi()["cartelle"] if c["id"] == cartella_id), None)

    def _scansiona(self, cartella_id, forza):
        c = self._cartella(cartella_id)
        if not c:
            return
        radice = Path(c["percorso"])
        if not radice.is_dir():
            self.log(f"Cartella non trovata: {radice}", "errore")
            return
        presenti = {str(p.relative_to(radice)): p for p in elenca_file(radice)}
        noti = self.indice.relpaths(c["id"])
        for rel in set(noti) - set(presenti):
            self.indice.rimuovi_documento(c["id"], rel)
            self.log(f"Tolto dall'indice (non c'è più): {rel}")
        da_fare = []
        for rel, p in sorted(presenti.items()):
            st = p.stat()
            n = noti.get(rel)
            if forza or not n or n["dimensione"] != st.st_size or abs((n["mtime"] or 0) - st.st_mtime) > 1e-3 or n["errore"]:
                da_fare.append(p)
        self.stato.update(cartella=c["nome"], fatti=0, totale=len(da_fare))
        if not da_fare:
            self.log(f"«{c['nome']}»: tutto aggiornato ({len(presenti)} documenti).")
        else:
            self.log(f"«{c['nome']}»: {len(da_fare)} documenti da indicizzare.")
        for i, p in enumerate(da_fare):
            self.stato["fatti"] = i
            self._indicizza(c, p, forza)
            self.stato["fatti"] = i + 1
        if da_fare:
            self.log(f"«{c['nome']}»: indicizzazione completata.", "ok")
        self.osserva(c)

    def _indicizza(self, c, p: Path, forza=False):
        radice = Path(c["percorso"])
        rel = str(p.relative_to(radice))
        self.stato.update(file=p.name, fase="lettura")
        st = p.stat()
        imp = impronta(p)
        noto = self.indice.documento(c["id"], rel)
        if noto and not forza and noto["impronta"] == imp and not noto["errore"]:
            return  # stesso contenuto: niente da fare
        inizio = time.time()
        impostazioni = config.leggi()
        try:
            unita, pagine = estrazione.estrai(
                p, impostazioni, avviso=lambda t: (self.stato.update(fase=t), self.log(f"{p.name}: {t}")))
            dim, sov = impostazioni["pezzi"]["dimensione"], impostazioni["pezzi"]["sovrapposizione"]
            per_pagina = [(pg.numero, pezzi.taglia(pg.testo, dim, sov)) for pg in pagine]
            testi = [f"{_titolo(p.name)} — {unita} {n}\n{t}" for n, ts in per_pagina for t in ts]
            self.stato["fase"] = "vettori"
            vet = None
            if testi:
                try:
                    vet = vettori.calcola(testi)
                    self.stato["errore_vettori"] = None
                except vettori.VettoriNonDisponibili as e:
                    self.stato["errore_vettori"] = str(e)
                    self.log(f"{p.name}: vettori rimandati ({e}). Funziona la sola ricerca per parole.", "avviso")
            self.indice.salva_documento(c["id"], rel, p.name, p.suffix.lower().lstrip("."), unita, st.st_size,
                                        st.st_mtime, imp, pagine, per_pagina, vet, time.time() - inizio)
            ocr = sum(1 for pg in pagine if pg.ocr)
            plurale = {"pagina": "pagine", "sezione": "sezioni"}.get(unita, unita)
            self.log(f"{p.name}: {len(pagine)} {unita if len(pagine) == 1 else plurale}, "
                     f"{len(testi)} pezzi" + (f", {ocr} con OCR" if ocr else "") + f" ({time.time() - inizio:.1f} s)", "ok",
                     {"tipo": "aggiornato" if noto else "nuovo", "nome": p.name, "cartella": c["nome"],
                      "pagine": len(pagine), "ocr": ocr, "pezzi": len(testi)})
        except Exception as e:
            self.indice.segna_errore(c["id"], rel, p.name, imp, st.st_mtime, str(e)[:500])
            self.log(f"{p.name}: non indicizzato ({e})", "errore")

    def _completa_vettori(self):
        while True:
            righe = self.indice.pezzi_senza_vettore(256)
            if not righe:
                self.log("Tutti i pezzi hanno il loro vettore.", "ok")
                return
            self.stato.update(fase="vettori mancanti", file=f"{len(righe)} pezzi")
            try:
                v = vettori.calcola([f"{_titolo(r['nome'])} — pagina {r['pagina']}\n{r['testo']}" for r in righe])
            except vettori.VettoriNonDisponibili as e:
                self.stato["errore_vettori"] = str(e)
                self.log(str(e), "errore")
                return
            self.stato["errore_vettori"] = None
            self.indice.imposta_vettori([(r["id"], v[i]) for i, r in enumerate(righe)])

    # ---------- osservatore delle cartelle ----------

    def osserva(self, c):
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        if c["id"] in self._osservatori:
            return
        io = self

        class Gestore(FileSystemEventHandler):
            def on_any_event(self, evento):
                if evento.is_directory:
                    return
                for attr in ("src_path", "dest_path"):
                    percorso = getattr(evento, attr, None)
                    if percorso:
                        io._segnala(c["id"], Path(os.fsdecode(percorso)))

        oss = Observer()
        oss.schedule(Gestore(), c["percorso"], recursive=True)
        oss.daemon = True
        oss.start()
        self._osservatori[c["id"]] = oss

    def smetti_di_osservare(self, cartella_id):
        oss = self._osservatori.pop(cartella_id, None)
        if oss:
            oss.stop()

    def _segnala(self, cartella_id, p: Path):
        if p.suffix.lower() not in config.ESTENSIONI or da_ignorare(p.name) or "/indice/" in str(p):
            return
        with self._lock:
            self._in_attesa[f"{cartella_id}\x00{p}"] = time.time()

    def _smaltisci_eventi(self):
        """Aspetta 2 secondi di calma dopo l'ultimo evento: un file copiato genera molti eventi."""
        while True:
            time.sleep(0.5)
            pronti = []
            with self._lock:
                for k, t in list(self._in_attesa.items()):
                    if time.time() - t > 2:
                        pronti.append(k)
                        del self._in_attesa[k]
            for k in pronti:
                cid, percorso = k.split("\x00", 1)
                c = self._cartella(cid)
                if not c:
                    continue
                try:
                    rel = str(Path(percorso).relative_to(c["percorso"]))
                except ValueError:
                    continue
                self.log(f"Cambiato: {rel}. Lo reindicizzo.")
                self.coda.put(("file", cid, rel, False))


def _titolo(nome: str) -> str:
    from .indice import nome_leggibile
    return "Documento: " + nome_leggibile(nome)
