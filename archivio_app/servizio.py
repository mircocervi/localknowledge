"""Il cuore condiviso da interfaccia web, server MCP e prova finale: cercare e rispondere.

Due modi di dare i documenti al modello:
- TUTTO: se l'intero archivio entra nella "memoria di lavoro" (il contesto) del modello, gli diamo
  tutte le pagine. Con poche decine di pagine è il modo migliore: il modello vede tutto e collega.
- RICERCA (RAG): se l'archivio è troppo grande, cerchiamo le pagine più pertinenti (ricerca ibrida)
  e diamo solo quelle, quante ne stanno nel contesto.
In "automatico" l'app sceglie da sola, guardando il contesto vero del modello.
"""
import time

from . import config, modelli, risposta, versioni, vettori
from .indice import Indice, Risultato

TOKEN_SISTEMA = 900          # regole + domanda + note: stima abbondante
MAX_PAGINA_CARATTERI = 4500  # una pagina più lunga di così si passa a pezzi, non intera


class Archivio:
    def __init__(self, indice: Indice):
        self.indice = indice

    def cartelle_attive(self, richieste: list[str] | None = None) -> list[str]:
        tutte = [c for c in config.leggi()["cartelle"]]
        if richieste is None:
            return [c["id"] for c in tutte if c.get("attiva", True)]
        validi = {c["id"] for c in tutte}
        return [c for c in richieste if c in validi]

    # ---------------- ricerca a pezzi (laboratorio, MCP) ----------------

    def cerca(self, domanda: str, cartelle: list[str] | None = None, estratti: int | None = None) -> dict:
        tutte = config.leggi()
        imp = tutte["ricerca"]
        cartelle = self.cartelle_attive(cartelle)
        t0 = time.perf_counter()
        avviso = None
        try:
            v = vettori.calcola([domanda], domanda=True)[0]
        except vettori.VettoriNonDisponibili as e:
            v, avviso = None, f"{e} Uso solo la ricerca per parole."
        t1 = time.perf_counter()
        risultati, classifiche = self.indice.cerca(domanda, v, cartelle, estratti or imp["estratti"], imp["candidati"],
                                                  sinonimi=tutte.get("sinonimi"))
        t2 = time.perf_counter()
        avvisi_versioni = versioni.analizza([r.nome for r in risultati], self.indice.nomi_documenti(cartelle))
        return {
            "estratti": risultati,
            "classifiche": classifiche,
            "versioni": avvisi_versioni,
            "nota_versioni": versioni.nota_per_modello(avvisi_versioni),
            "tempi": {"vettore_domanda_ms": round((t1 - t0) * 1000), "ricerca_ms": round((t2 - t1) * 1000)},
            "avviso": avviso,
            "cartelle": cartelle,
            "modo": "ricerca",
        }

    def messaggi(self, domanda: str, ricerca: dict) -> list[dict]:
        return risposta.costruisci_messaggi(domanda, ricerca["estratti"], ricerca["nota_versioni"],
                                            tutto=ricerca.get("modo") == "tutto")

    # ---------------- preparazione per il modello ----------------

    def _pagine_tutte(self, cartelle) -> list[Risultato]:
        out = []
        for d in self.indice.documenti():
            if d["cartella_id"] not in cartelle or d["errore"]:
                continue
            for p in self.indice.pagine_di(d["id"]):
                if (p["testo"] or "").strip():
                    out.append(Risultato(None, d["id"], d["nome"], d["relpath"], d["cartella_id"], p["numero"],
                                         d["unita"] or "pagina", p["testo"], bool(p["ocr"])))
        return out

    def prepara(self, domanda: str, fornitore: str, modello: str, cartelle: list[str] | None = None,
                modo: str = "auto", ragionamento: bool = True) -> dict:
        """Decide cosa leggerà il modello e restituisce tutto il necessario per chiedergli la risposta."""
        imp = config.leggi()["ricerca"]
        cartelle = self.cartelle_attive(cartelle)
        ctx = modelli.contesto(fornitore, modello)
        riserva = 6000 if ragionamento else 1500           # spazio per ragionare e rispondere
        spazio = int(ctx * 0.9) - TOKEN_SISTEMA - riserva   # token disponibili per i documenti
        limite_tutto = imp.get("limite_tutto", 60000)

        tutte = self._pagine_tutte(cartelle)
        token_tutto = sum(modelli.stima_token(p.testo) + 25 for p in tutte)
        entra = token_tutto <= min(spazio, limite_tutto)
        avviso = None
        if modo == "tutto" and not entra:
            avviso = (f"L'archivio ({token_tutto:,} token) non entra nel contesto di questo modello "
                      f"({ctx:,} token): uso la ricerca.").replace(",", ".")
        if (modo in ("auto", "tutto")) and entra and tutte:
            t0 = time.perf_counter()
            avvisi = versioni.analizza([p.nome for p in tutte], self.indice.nomi_documenti(cartelle))
            return {
                "modo": "tutto", "estratti": tutte, "versioni": avvisi, "nota_versioni": versioni.nota_per_modello(avvisi),
                "tempi": {"vettore_domanda_ms": 0, "ricerca_ms": round((time.perf_counter() - t0) * 1000)},
                "avviso": avviso, "cartelle": cartelle, "contesto": ctx, "token_documenti": token_tutto,
                "documenti": len({p.doc_id for p in tutte}),
            }

        # RICERCA: pezzi migliori -> pagine intere, finché c'è spazio
        r = self.cerca(domanda, cartelle, estratti=max(imp["estratti"] * 3, 20))
        budget = max(1200, min(spazio, imp.get("limite_ricerca", 14000)))
        pagine, viste, usati = [], set(), 0
        for e in r["estratti"]:
            chiave = (e.doc_id, e.pagina)
            if chiave in viste:
                continue
            testo_pagina = self.indice.testo_pagina(e.doc_id, e.pagina) or e.testo
            testo = testo_pagina if len(testo_pagina) <= MAX_PAGINA_CARATTERI else e.testo
            costo = modelli.stima_token(testo) + 25
            if pagine and (usati + costo > budget or len(pagine) >= imp["estratti"]):
                break
            viste.add(chiave)
            usati += costo
            pagine.append(Risultato(e.pezzo_id, e.doc_id, e.nome, e.relpath, e.cartella_id, e.pagina, e.unita, testo,
                                    e.ocr, e.punteggio, e.rango_parole, e.rango_significato, e.sim))
        avvisi = versioni.analizza([p.nome for p in pagine], self.indice.nomi_documenti(cartelle))
        r.update(estratti=pagine, versioni=avvisi, nota_versioni=versioni.nota_per_modello(avvisi), modo="ricerca",
                 contesto=ctx, token_documenti=usati, token_archivio=token_tutto,
                 documenti=len({p.doc_id for p in pagine}),
                 avviso=" ".join(x for x in (avviso, r["avviso"]) if x) or None)
        return r
