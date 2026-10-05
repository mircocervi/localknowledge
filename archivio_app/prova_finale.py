"""La prova finale: 3 domande sulla data-room di Crinale, su ogni modello acceso.

    uv run archivio.py --prova-finale                    tutti i modelli accesi su Ollama e LM Studio
    uv run archivio.py --prova-finale --solo spark,minicpm
Dalla pagina /admin → Banco prova si fa la stessa cosa con un clic.
"""
import json
import re
import sys
import time
from pathlib import Path

from . import config, modelli, risposta

PROVE = [
    {
        "id": "nordwand",
        "domanda": config.DOMANDE_ESEMPIO[0],
        "attesa": "Rinnovo 2024, art. 14.3, pagina 2: con il cambio di controllo Nordwand può recedere con 30 giorni di preavviso, senza indennizzo.",
        "fonte": ("13_Rinnovo_Nordwand_2024.pdf", 2),
        "contenuto": lambda t: bool(re.search(r"14\.3", t)) or (
            bool(re.search(r"reced|recesso", t, re.I)) and bool(re.search(r"\b30\b|trenta", t, re.I))),
    },
    {
        "id": "cause",
        "domanda": config.DOMANDE_ESEMPIO[1],
        "attesa": "Sì: ricorso di Giulia Ferraro al Tribunale di Roma (scansione, serve l'OCR), 340.000 euro.",
        "fonte": ("20_Ricorso_Ferraro_Tribunale_Roma.pdf", 1),
        "contenuto": lambda t: bool(re.search(r"ferraro|tribunale|ricorso", t, re.I)) and not risposta.e_non_presente(t),
    },
    {
        "id": "germania",
        "domanda": config.DOMANDE_ESEMPIO[2],
        "attesa": "Non presente nei documenti.",
        "fonte": None,
        "contenuto": lambda t: risposta.e_non_presente(t),
    },
]


def valuta(prova: dict, testo: str, ver: dict) -> dict:
    contenuto = bool(prova["contenuto"](testo))
    if prova["fonte"] is None:
        citazione = ver["non_presente"] and not ver["citati"]
    else:
        nome, pagina = prova["fonte"]
        citazione = any(f["nome"] == nome and f["pagina"] == pagina for f in ver["fonti"])
    return {"contenuto": contenuto, "citazione": citazione, "inventate": ver["inventate"],
            "ok": contenuto and citazione and not ver["inventate"]}


def modelli_accesi(filtro: list[str] | None = None) -> list[dict]:
    out = []
    for f in ("ollama", "lmstudio"):
        e = modelli.elenco(f)
        for m in e.get("modelli", []):
            if filtro and not any(x.lower() in m["id"].lower() for x in filtro):
                continue
            out.append({"fornitore": f, "modello": m["id"]})
    return out


def esegui(archivio, bersagli: list[dict], ragionamento: bool = False, avanzamento=None, modo: str = "auto") -> list[dict]:
    risultati = []
    nome = time.strftime("prova_%Y-%m-%d_%H%M%S.json")
    totale = len(bersagli) * len(PROVE)
    fatti = 0
    for b in bersagli:
        for p in PROVE:
            if avanzamento:
                avanzamento(fatti, totale, b, p)
            voce = {"fornitore": b["fornitore"], "modello": b["modello"], "prova": p["id"], "domanda": p["domanda"],
                    "attesa": p["attesa"]}
            try:
                r = archivio.prepara(p["domanda"], b["fornitore"], b["modello"], None, modo, ragionamento)
                voce.update(modo=r["modo"], contesto=r.get("contesto"), token_documenti=r.get("token_documenti"))
                testo, ragion, stat = modelli.risposta_completa(
                    b["fornitore"], b["modello"], archivio.messaggi(p["domanda"], r), ragionamento=ragionamento,
                    contesto_token=r.get("contesto"))
                ver = risposta.verifica(testo, r["estratti"])
                voce.update(risposta=testo, secondi=stat.get("secondi"), token=stat.get("token"),
                            fonti=ver["fonti"], **valuta(p, testo, ver))
            except Exception as e:
                voce.update(risposta="", errore=str(e)[:300], ok=False, contenuto=False, citazione=False, fonti=[])
            risultati.append(voce)
            fatti += 1
            salva(risultati, ragionamento, nome)  # dopo ogni risposta: se si interrompe, il lavoro resta
        if len(bersagli) > 1:
            modelli.libera(b["fornitore"], b["modello"])
    if avanzamento:
        avanzamento(fatti, totale, None, None)
    return risultati


def salva(risultati, ragionamento, nome):
    d = config.DIR_INDICE / "prove"
    d.mkdir(parents=True, exist_ok=True)
    (d / nome).write_text(json.dumps({"quando": time.time(), "ragionamento": ragionamento, "risultati": risultati},
                                     ensure_ascii=False, indent=2), encoding="utf-8")


def ultima() -> dict | None:
    d = config.DIR_INDICE / "prove"
    file = sorted(d.glob("prova_*.json")) if d.exists() else []
    return json.loads(file[-1].read_text(encoding="utf-8")) if file else None


def main() -> int:
    import argparse

    from .indice import Indice
    from .servizio import Archivio

    p = argparse.ArgumentParser()
    p.add_argument("--prova-finale", action="store_true")
    p.add_argument("--solo", help="filtra i modelli per nome, separati da virgola")
    p.add_argument("--ragionamento", action="store_true", help="lascia ragionare i modelli (più lento)")
    p.add_argument("--modo", default="auto", choices=["auto", "tutto", "ricerca"])
    a, _ = p.parse_known_args()
    bersagli = modelli_accesi(a.solo.split(",") if a.solo else None)
    if not bersagli:
        print("Nessun modello acceso su Ollama o LM Studio.")
        return 1
    archivio = Archivio(Indice())

    def avanti(i, n, b, pr):
        if b:
            print(f"[{i + 1}/{n}] {b['fornitore']} · {b['modello']} · {pr['id']}", file=sys.stderr, flush=True)

    ris = esegui(archivio, bersagli, a.ragionamento, avanti, a.modo)
    print()
    for r in ris:
        segno = "OK " if r["ok"] else "NO "
        fonti = ", ".join(f"{f['nome']} p.{f['pagina']}" for f in r.get("fonti", [])) or "—"
        print(f"{segno} {r['fornitore']:<9} {r['modello'][:42]:<42} {r['prova']:<9} {r.get('modo', ''):<8}"
              f"contenuto={'sì' if r['contenuto'] else 'no'} citazione={'sì' if r['citazione'] else 'no'} "
              f"{r.get('secondi') or 0:>5.1f}s  [{fonti}]" + (f"  ERRORE {r['errore']}" if r.get("errore") else ""))
    return 0
