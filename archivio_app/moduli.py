"""Moduli che si accendono e si spengono da /admin → Moduli.

Un modulo aggiunge una scheda all'app del cliente e, se serve, un proprio server MCP
(su /mcp/<id>). Oggi c'è solo il segnaposto della BI, che si costruisce la prossima serata.
"""
from . import config

MODULI = {
    "bi": {
        "nome": "BI · Business Intelligence",
        "breve": "Cruscotti e domande sui numeri di Crinale",
        "descrizione": ("Domande in italiano sui dati di vendita di Crinale, con grafici. Userà gli stessi dati "
                        "del server MCP di Crinale (DuckDB, porta 5400), così documenti e numeri si interrogano insieme."),
        "stato": "in preparazione",
        "mcp": "/mcp/bi",
        "fonte": "http://127.0.0.1:5400/mcp",
    },
}


def elenco() -> list[dict]:
    accesi = config.leggi()["moduli"]
    return [{"id": k, **v, "acceso": bool(accesi.get(k))} for k, v in MODULI.items()]


def acceso(mid: str) -> bool:
    return bool(config.leggi()["moduli"].get(mid))
