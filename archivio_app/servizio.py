"""Il cuore condiviso da interfaccia web, server MCP e prova finale: cercare e rispondere."""
import time

from . import config, risposta, versioni, vettori
from .indice import Indice


class Archivio:
    def __init__(self, indice: Indice):
        self.indice = indice

    def cartelle_attive(self, richieste: list[str] | None = None) -> list[str]:
        tutte = [c for c in config.leggi()["cartelle"]]
        if richieste is None:
            return [c["id"] for c in tutte if c.get("attiva", True)]
        validi = {c["id"] for c in tutte}
        return [c for c in richieste if c in validi]

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
        }

    def messaggi(self, domanda: str, ricerca: dict) -> list[dict]:
        return risposta.costruisci_messaggi(domanda, ricerca["estratti"], ricerca["nota_versioni"])
