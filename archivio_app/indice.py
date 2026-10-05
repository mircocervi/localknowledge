"""L'indice: un solo file SQLite in indice/archivio.db.

- documenti, pagine, pezzi: tabelle normali
- pezzi_fts: indice per PAROLE (FTS5, punteggio BM25) per codici, importi, nomi
- pezzi.vettore: il vettore di ogni pezzo; all'avvio tutti i vettori vanno in memoria
  in una matrice numpy, e la ricerca per SIGNIFICATO è un prodotto matrice-vettore (millisecondi).
Le due classifiche si fondono con la Reciprocal Rank Fusion (RRF).
"""
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field

import numpy as np

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS documenti (
    id INTEGER PRIMARY KEY,
    cartella_id TEXT NOT NULL,
    relpath TEXT NOT NULL,
    nome TEXT NOT NULL,
    estensione TEXT,
    unita TEXT DEFAULT 'pagina',
    dimensione INTEGER,
    mtime REAL,
    impronta TEXT,
    pagine INTEGER DEFAULT 0,
    pagine_ocr INTEGER DEFAULT 0,
    indicizzato_il REAL,
    secondi REAL,
    errore TEXT,
    UNIQUE(cartella_id, relpath)
);
CREATE TABLE IF NOT EXISTS pagine (
    doc_id INTEGER NOT NULL REFERENCES documenti(id) ON DELETE CASCADE,
    numero INTEGER NOT NULL,
    testo TEXT,
    ocr INTEGER DEFAULT 0,
    PRIMARY KEY (doc_id, numero)
);
CREATE TABLE IF NOT EXISTS pezzi (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES documenti(id) ON DELETE CASCADE,
    pagina INTEGER NOT NULL,
    posizione INTEGER NOT NULL,
    testo TEXT NOT NULL,
    vettore BLOB
);
CREATE INDEX IF NOT EXISTS pezzi_doc ON pezzi(doc_id);
CREATE VIRTUAL TABLE IF NOT EXISTS pezzi_fts USING fts5(
    testo, nome, tokenize = 'unicode61 remove_diacritics 2'
);
"""

PAROLE_VUOTE = set("""
a ad al allo ai agli all alla alle anche c che chi ci come con contro cosa cui da dal dallo dai dagli dall dalla dalle
del dello dei degli dell della delle di dove e ed è era essere fa gli ha hanno ho i il in io l la le lei lo loro lui ma
mi mio ne negli nel nello nei nell nella nelle no non o per più può quale quali qual quando quanto quella quelle quelli
quello questa queste questi questo se si sia sono su sul sullo sui sugli sull sulla sulle tra fra tu un una uno vi
cosa sono c'è ci sono ce qualche quale quali come mai cos dimmi dammi trova
""".split())


@dataclass
class Risultato:
    pezzo_id: int
    doc_id: int
    nome: str
    relpath: str
    cartella_id: str
    pagina: int
    unita: str
    testo: str
    ocr: bool
    punteggio: float = 0.0
    rango_parole: int | None = None
    rango_significato: int | None = None
    sim: float | None = None
    extra: dict = field(default_factory=dict)

    def dict(self):
        return {k: getattr(self, k) for k in (
            "pezzo_id", "doc_id", "nome", "relpath", "cartella_id", "pagina", "unita", "testo", "ocr",
            "punteggio", "rango_parole", "rango_significato", "sim")}


def nome_leggibile(nome: str) -> str:
    """'13_Rinnovo_Nordwand_2024.pdf' -> 'Rinnovo Nordwand 2024' (per l'indice per parole)."""
    base = re.sub(r"\.[a-z0-9]+$", "", nome, flags=re.I)
    return re.sub(r"[_\-]+", " ", base)


def radice(tok: str) -> str:
    """Radice grezza dell'italiano: contratto/contratti -> contrat, cause/causa -> caus."""
    if len(tok) >= 7:
        return tok[:-2]
    if len(tok) >= 5:
        return tok[:-1]
    return tok


def _parole(testo: str) -> list[str]:
    out = []
    for tok in re.findall(r"\w[\w.,/\-']*\w|\w", testo.lower()):
        tok = tok.strip("'")
        if "'" in tok:  # l'articolo apostrofato: "dell'accordo" -> "accordo"
            tok = tok.split("'")[-1]
        if tok:
            out.append(tok)
    return out


def espandi(parole: list[str], sinonimi: list[str] | None) -> list[str]:
    """Aggiunge i sinonimi: se una parola della domanda è in un gruppo, entra tutto il gruppo.
    Un gruppo è una riga: 'causa, contenzioso, ricorso, tribunale'."""
    if not sinonimi:
        return []
    radici = {radice(p) for p in parole if p not in PAROLE_VUOTE}
    extra = []
    for riga in sinonimi:
        gruppo = [g.strip().lower() for g in re.split(r"[,;]", riga) if g.strip()]
        membri = [_parole(g) for g in gruppo]
        if any(m and radice(m[-1]) in radici for m in membri if len(m) == 1):
            for m in membri:
                if len(m) == 1:
                    extra.append(m[0])
                elif m:
                    extra.append(" ".join(m))
    return extra


def domanda_fts(domanda: str, sinonimi: list[str] | None = None) -> str:
    """Trasforma la domanda in una query FTS5: parole importanti in OR, codici come frase esatta.

    'cause' -> caus*  ·  'contratto' -> contrat*  (radice grezza dell'italiano)
    '14.3' -> "14.3"  ·  sinonimi: 'cause' porta con sé ricors*, tribunal*, contenzios*...
    """
    parole = _parole(domanda)
    termini = []
    for tok in parole + espandi(parole, sinonimi):
        if tok in PAROLE_VUOTE:
            continue
        if " " in tok:  # sinonimo di più parole: frase esatta
            termini.append('"' + tok.replace('"', "") + '"')
        elif re.search(r"[.,/\-]", tok) or re.fullmatch(r"\d+", tok):
            termini.append('"' + tok.replace('"', "") + '"')
        elif re.search(r"\d", tok):  # codici come MAG02: esatti, mai troncati
            termini.append(tok)
        elif len(tok) >= 5:
            termini.append(radice(tok) + "*")
        elif len(tok) >= 2:
            termini.append(tok)
    visti, unici = set(), []
    for t in termini:
        if t not in visti:
            visti.add(t)
            unici.append(t)
    return " OR ".join(unici)


class Indice:
    def __init__(self, percorso=None):
        self.percorso = percorso or config.FILE_DB
        config.DIR_INDICE.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.percorso), check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)
        self.lock = threading.RLock()
        self._matrice = None
        self._ids = None
        self._cartelle = None
        self.carica_vettori()

    # ---------- scrittura ----------

    def documento(self, cartella_id: str, relpath: str):
        with self.lock:
            return self.db.execute(
                "SELECT * FROM documenti WHERE cartella_id=? AND relpath=?", (cartella_id, relpath)).fetchone()

    def salva_documento(self, cartella_id, relpath, nome, estensione, unita, dimensione, mtime, impronta,
                        pagine, pezzi_per_pagina, vettori, secondi):
        """Sostituisce in un colpo solo tutto ciò che riguarda un documento (transazione)."""
        with self.lock, self.db:
            vecchio = self.db.execute(
                "SELECT id FROM documenti WHERE cartella_id=? AND relpath=?", (cartella_id, relpath)).fetchone()
            if vecchio:
                self._cancella_righe(vecchio["id"])
            cur = self.db.execute(
                """INSERT INTO documenti (cartella_id, relpath, nome, estensione, unita, dimensione, mtime, impronta,
                   pagine, pagine_ocr, indicizzato_il, secondi, errore) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL)""",
                (cartella_id, relpath, nome, estensione, unita, dimensione, mtime, impronta,
                 len(pagine), sum(1 for p in pagine if p.ocr), time.time(), secondi))
            doc_id = cur.lastrowid
            self.db.executemany("INSERT INTO pagine (doc_id, numero, testo, ocr) VALUES (?,?,?,?)",
                                [(doc_id, p.numero, p.testo, int(p.ocr)) for p in pagine])
            nome_fts = nome_leggibile(nome)
            k = 0
            for numero, testi in pezzi_per_pagina:
                for pos, testo in enumerate(testi):
                    vet = vettori[k].astype(np.float32).tobytes() if vettori is not None else None
                    k += 1
                    c = self.db.execute(
                        "INSERT INTO pezzi (doc_id, pagina, posizione, testo, vettore) VALUES (?,?,?,?,?)",
                        (doc_id, numero, pos, testo, vet))
                    self.db.execute("INSERT INTO pezzi_fts (rowid, testo, nome) VALUES (?,?,?)",
                                    (c.lastrowid, testo, nome_fts))
        self.carica_vettori()
        return doc_id

    def segna_errore(self, cartella_id, relpath, nome, impronta, mtime, errore):
        with self.lock, self.db:
            vecchio = self.db.execute(
                "SELECT id FROM documenti WHERE cartella_id=? AND relpath=?", (cartella_id, relpath)).fetchone()
            if vecchio:
                self._cancella_righe(vecchio["id"])
            self.db.execute(
                """INSERT INTO documenti (cartella_id, relpath, nome, estensione, impronta, mtime, indicizzato_il, errore)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (cartella_id, relpath, nome, nome.rsplit(".", 1)[-1].lower(), impronta, mtime, time.time(), errore))
        self.carica_vettori()

    def _cancella_righe(self, doc_id):
        self.db.execute("DELETE FROM pezzi_fts WHERE rowid IN (SELECT id FROM pezzi WHERE doc_id=?)", (doc_id,))
        self.db.execute("DELETE FROM pezzi WHERE doc_id=?", (doc_id,))
        self.db.execute("DELETE FROM pagine WHERE doc_id=?", (doc_id,))
        self.db.execute("DELETE FROM documenti WHERE id=?", (doc_id,))

    def rimuovi_documento(self, cartella_id, relpath):
        with self.lock, self.db:
            r = self.db.execute(
                "SELECT id FROM documenti WHERE cartella_id=? AND relpath=?", (cartella_id, relpath)).fetchone()
            if r:
                self._cancella_righe(r["id"])
        self.carica_vettori()

    def rimuovi_cartella(self, cartella_id):
        with self.lock, self.db:
            for r in self.db.execute("SELECT id FROM documenti WHERE cartella_id=?", (cartella_id,)).fetchall():
                self._cancella_righe(r["id"])
        self.carica_vettori()

    def relpaths(self, cartella_id) -> dict:
        with self.lock:
            return {r["relpath"]: dict(r) for r in self.db.execute(
                "SELECT relpath, impronta, mtime, dimensione, errore FROM documenti WHERE cartella_id=?", (cartella_id,))}

    # ---------- vettori in memoria ----------

    def carica_vettori(self):
        with self.lock:
            righe = self.db.execute(
                "SELECT p.id, p.vettore, d.cartella_id FROM pezzi p JOIN documenti d ON d.id=p.doc_id "
                "WHERE p.vettore IS NOT NULL").fetchall()
            if not righe:
                self._matrice, self._ids, self._cartelle = None, np.zeros(0, dtype=np.int64), np.array([])
                return
            self._ids = np.array([r["id"] for r in righe], dtype=np.int64)
            self._cartelle = np.array([r["cartella_id"] for r in righe])
            self._matrice = np.vstack([np.frombuffer(r["vettore"], dtype=np.float32) for r in righe])

    # ---------- lettura ----------

    def _risultati(self, ids: list[int]) -> dict[int, Risultato]:
        if not ids:
            return {}
        segnaposto = ",".join("?" * len(ids))
        with self.lock:
            righe = self.db.execute(
                f"""SELECT p.id, p.doc_id, p.pagina, p.testo, d.nome, d.relpath, d.cartella_id, d.unita,
                    COALESCE(pg.ocr, 0) AS ocr
                    FROM pezzi p JOIN documenti d ON d.id=p.doc_id
                    LEFT JOIN pagine pg ON pg.doc_id=p.doc_id AND pg.numero=p.pagina
                    WHERE p.id IN ({segnaposto})""", ids).fetchall()
        return {r["id"]: Risultato(r["id"], r["doc_id"], r["nome"], r["relpath"], r["cartella_id"], r["pagina"],
                                   r["unita"] or "pagina", r["testo"], bool(r["ocr"])) for r in righe}

    def cerca_parole(self, domanda: str, cartelle: list[str] | None, limite: int = 40,
                     sinonimi: list[str] | None = None) -> list[tuple[int, float]]:
        q = domanda_fts(domanda, sinonimi)
        if not q:
            return []
        filtro, args = "", [q]
        if cartelle is not None:
            if not cartelle:
                return []
            filtro = f" AND d.cartella_id IN ({','.join('?' * len(cartelle))})"
            args += cartelle
        with self.lock:
            try:
                righe = self.db.execute(
                    f"""SELECT f.rowid AS id, bm25(pezzi_fts, 1.0, 0.6) AS s FROM pezzi_fts f
                        JOIN pezzi p ON p.id=f.rowid JOIN documenti d ON d.id=p.doc_id
                        WHERE pezzi_fts MATCH ?{filtro} ORDER BY s LIMIT ?""", args + [limite]).fetchall()
            except sqlite3.OperationalError:
                return []
        return [(r["id"], -r["s"]) for r in righe]

    def cerca_significato(self, vettore: np.ndarray, cartelle: list[str] | None, limite: int = 40):
        with self.lock:
            m, ids, cart = self._matrice, self._ids, self._cartelle
        if m is None or vettore is None:
            return []
        sim = m @ vettore
        if cartelle is not None:
            sim = np.where(np.isin(cart, cartelle), sim, -np.inf)
        n = min(limite, int(np.isfinite(sim).sum()))
        if n <= 0:
            return []
        top = np.argpartition(-sim, n - 1)[:n]
        top = top[np.argsort(-sim[top])]
        return [(int(ids[i]), float(sim[i])) for i in top]

    def cerca(self, domanda: str, vettore: np.ndarray | None, cartelle=None, estratti=8, candidati=40, k_rrf=60,
              sinonimi: list[str] | None = None):
        """Ricerca ibrida: classifica per parole + classifica per significato, fuse con RRF.

        RRF: ogni pezzo prende 1/(60 + posizione) da ciascuna classifica in cui compare.
        Chi è in alto in entrambe vince; chi è primo in una sola resta comunque in gara.
        """
        parole = self.cerca_parole(domanda, cartelle, candidati, sinonimi)
        significato = self.cerca_significato(vettore, cartelle, candidati) if vettore is not None else []
        punteggi: dict[int, float] = {}
        rp, rs, sims = {}, {}, {}
        for rango, (pid, _) in enumerate(parole, 1):
            punteggi[pid] = punteggi.get(pid, 0) + 1 / (k_rrf + rango)
            rp[pid] = rango
        for rango, (pid, s) in enumerate(significato, 1):
            punteggi[pid] = punteggi.get(pid, 0) + 1 / (k_rrf + rango)
            rs[pid] = rango
            sims[pid] = s
        migliori = sorted(punteggi, key=lambda p: -punteggi[p])[:estratti]
        dati = self._risultati(migliori)
        out = []
        for pid in migliori:
            r = dati.get(pid)
            if not r:
                continue
            r.punteggio, r.rango_parole, r.rango_significato, r.sim = punteggi[pid], rp.get(pid), rs.get(pid), sims.get(pid)
            out.append(r)
        return out, {"parole": parole, "significato": significato}

    def risultati(self, ids):
        return self._risultati(ids)

    # ---------- statistiche e consultazione ----------

    def statistiche(self) -> dict:
        with self.lock:
            per_cartella = {r["cartella_id"]: dict(r) for r in self.db.execute(
                """SELECT d.cartella_id, COUNT(DISTINCT d.id) AS documenti, COALESCE(SUM(d.pagine),0) AS pagine,
                   COALESCE(SUM(d.pagine_ocr),0) AS pagine_ocr, SUM(d.errore IS NOT NULL) AS errori
                   FROM documenti d GROUP BY d.cartella_id""")}
            pezzi = {r["cartella_id"]: (r["n"], r["v"]) for r in self.db.execute(
                """SELECT d.cartella_id, COUNT(p.id) AS n, SUM(p.vettore IS NOT NULL) AS v
                   FROM pezzi p JOIN documenti d ON d.id=p.doc_id GROUP BY d.cartella_id""")}
        for cid, (n, v) in pezzi.items():
            per_cartella.setdefault(cid, {"documenti": 0, "pagine": 0, "pagine_ocr": 0, "errori": 0})
            per_cartella[cid]["pezzi"], per_cartella[cid]["con_vettore"] = n, v or 0
        totale = {k: sum(c.get(k, 0) or 0 for c in per_cartella.values())
                  for k in ("documenti", "pagine", "pagine_ocr", "pezzi", "con_vettore", "errori")}
        dim = self.percorso.stat().st_size if self.percorso.exists() else 0
        wal = self.percorso.with_name(self.percorso.name + "-wal")
        if wal.exists():
            dim += wal.stat().st_size
        totale["byte"] = dim
        totale["dimensioni_vettore"] = int(self._matrice.shape[1]) if self._matrice is not None else 0
        return {"totale": totale, "cartelle": per_cartella}

    def documenti(self, cartella_id=None):
        with self.lock:
            q = "SELECT * FROM documenti" + (" WHERE cartella_id=?" if cartella_id else "") + " ORDER BY nome"
            docs = [dict(r) for r in self.db.execute(q, (cartella_id,) if cartella_id else ())]
            conti = {r["doc_id"]: r["n"] for r in self.db.execute("SELECT doc_id, COUNT(*) n FROM pezzi GROUP BY doc_id")}
        for d in docs:
            d["pezzi"] = conti.get(d["id"], 0)
        return docs

    def documento_da_id(self, doc_id):
        with self.lock:
            r = self.db.execute("SELECT * FROM documenti WHERE id=?", (doc_id,)).fetchone()
            return dict(r) if r else None

    def pagine_di(self, doc_id):
        with self.lock:
            return [dict(r) for r in self.db.execute(
                "SELECT numero, testo, ocr FROM pagine WHERE doc_id=? ORDER BY numero", (doc_id,))]

    def pezzi_di(self, doc_id):
        with self.lock:
            righe = self.db.execute(
                "SELECT id, pagina, posizione, testo, vettore FROM pezzi WHERE doc_id=? ORDER BY pagina, posizione",
                (doc_id,)).fetchall()
        out = []
        for r in righe:
            v = np.frombuffer(r["vettore"], dtype=np.float32) if r["vettore"] else None
            out.append({"id": r["id"], "pagina": r["pagina"], "posizione": r["posizione"], "testo": r["testo"],
                        "vettore_anteprima": [round(float(x), 4) for x in v[:12]] if v is not None else None,
                        "dimensioni": int(v.shape[0]) if v is not None else 0})
        return out

    def pezzi_senza_vettore(self, limite=500):
        with self.lock:
            return [dict(r) for r in self.db.execute(
                """SELECT p.id, p.testo, d.nome, p.pagina FROM pezzi p JOIN documenti d ON d.id=p.doc_id
                   WHERE p.vettore IS NULL LIMIT ?""", (limite,))]

    def imposta_vettori(self, coppie):
        with self.lock, self.db:
            self.db.executemany("UPDATE pezzi SET vettore=? WHERE id=?",
                                [(v.astype(np.float32).tobytes(), pid) for pid, v in coppie])
        self.carica_vettori()

    def nomi_documenti(self, cartelle=None) -> list[dict]:
        with self.lock:
            q = "SELECT id, nome, relpath, cartella_id, mtime FROM documenti WHERE errore IS NULL"
            args = ()
            if cartelle is not None:
                if not cartelle:
                    return []
                q += f" AND cartella_id IN ({','.join('?' * len(cartelle))})"
                args = tuple(cartelle)
            return [dict(r) for r in self.db.execute(q, args)]
