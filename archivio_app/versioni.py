"""Versioni dello stesso documento: stesso nome, anni diversi.

Dal nome del file togliamo numeri d'ordine, anni, date e parole generiche
(contratto, rinnovo, bozza...): ciò che resta è la "famiglia".
    11_Contratto_Nordwand_2016.pdf  -> nordwand  (2016)
    13_Rinnovo_Nordwand_2024.pdf    -> nordwand  (2024)
"""
import re
from datetime import datetime

GENERICHE = set("""
contratto contratti rinnovo rinnovato rinnovata versione vers ver rev revisione bozza draft finale final def definitivo
definitiva aggiornamento aggiornato aggiornata copia nuovo nuova modifica modificato addendum integrazione emendamento
firmato firmata scansione scan v
""".split())

DATA = re.compile(r"(19|20)\d{2}[-_.](0[1-9]|1[0-2])[-_.](0[1-9]|[12]\d|3[01])")
ANNO = re.compile(r"(?<!\d)(19[5-9]\d|20\d{2})(?!\d)")


def famiglia(nome: str) -> tuple[str, str | None]:
    """Restituisce (chiave_famiglia, data_ordinabile 'AAAA' o 'AAAA-MM-GG' oppure None)."""
    base = re.sub(r"\.[A-Za-z0-9]+$", "", nome)
    quando = None
    m = DATA.search(base)
    if m:
        quando = re.sub(r"[_.]", "-", m.group(0))
        base = base.replace(m.group(0), " ")
    else:
        anni = ANNO.findall(base)
        if anni:
            quando = max(anni)
    parti = [p for p in re.split(r"[\s_\-.()\[\]]+", base.lower()) if p]
    parti = [p for p in parti
             if not re.fullmatch(r"\d+", p) and not re.fullmatch(r"v\d+", p) and p not in GENERICHE]
    return " ".join(parti), quando


def raggruppa(nomi: list[dict]) -> dict[str, list[dict]]:
    """nomi: [{'nome':..., 'mtime':...}]. Restituisce solo le famiglie con 2+ documenti datati."""
    gruppi: dict[str, list[dict]] = {}
    for d in nomi:
        chiave, quando = famiglia(d["nome"])
        if not chiave or not quando:
            continue
        gruppi.setdefault(chiave, []).append({**d, "quando": quando})
    out = {}
    for k, v in gruppi.items():
        if len({x["nome"] for x in v}) >= 2:
            out[k] = sorted(v, key=lambda x: (x["quando"], x.get("mtime") or 0))
    return out


def analizza(nomi_estratti: list[str], tutti: list[dict]) -> list[dict]:
    """Per ogni famiglia presente negli estratti con più versioni (negli estratti o nell'archivio):
    quali versioni sono negli estratti, quali no, qual è la più recente."""
    gruppi = raggruppa(tutti)
    presenti = set(nomi_estratti)
    avvisi = []
    for chiave, membri in gruppi.items():
        negli_estratti = [m for m in membri if m["nome"] in presenti]
        if not negli_estratti:
            continue
        piu_recente = membri[-1]
        if len(negli_estratti) < 2 and negli_estratti[0]["nome"] == piu_recente["nome"]:
            # un'unica versione tra gli estratti ed è già la più recente: lo diciamo comunque, in breve
            tipo = "solo_recente"
        elif len(negli_estratti) >= 2:
            tipo = "piu_versioni"
        else:
            tipo = "manca_recente"  # tra gli estratti c'è solo una versione vecchia
        avvisi.append({
            "famiglia": chiave,
            "tipo": tipo,
            "versioni": [{"nome": m["nome"], "quando": m["quando"], "negli_estratti": m["nome"] in presenti,
                          "doc_id": m.get("id")} for m in membri],
            "piu_recente": piu_recente["nome"],
        })
    return avvisi


def nota_per_modello(avvisi: list[dict]) -> str:
    righe = []
    for a in avvisi:
        if a["tipo"] == "solo_recente":
            continue
        elenco = ", ".join(f"{v['nome']} ({_leggibile(v['quando'])})" for v in a["versioni"] if v["negli_estratti"])
        righe.append(f"- Versioni dello stesso documento tra gli estratti: {elenco}. "
                     f"La più recente nell'archivio è {a['piu_recente']}.")
    return "\n".join(righe)


def _leggibile(quando: str) -> str:
    if len(quando) == 10:
        try:
            return datetime.strptime(quando, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return quando
    return quando
