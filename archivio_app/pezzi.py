"""Taglio del testo in pezzi di circa 1.000 caratteri che si sovrappongono un po'.

Un pezzo non attraversa mai due pagine: così ogni pezzo ha una sola pagina da citare.
"""
import re

FINE_FRASE = re.compile(r"[.;:!?]\s|\n")


def taglia(testo: str, dimensione: int = 1000, sovrapposizione: int = 150) -> list[str]:
    testo = testo.strip()
    if not testo:
        return []
    if len(testo) <= dimensione:
        return [testo]
    pezzi, inizio = [], 0
    while inizio < len(testo):
        fine = min(inizio + dimensione, len(testo))
        if fine < len(testo):
            # se ciò che resta è poco, lo teniamo nel pezzo corrente invece di lasciarlo orfano
            if len(testo) - fine < dimensione // 4:
                fine = len(testo)
            else:
                fine = _taglio_naturale(testo, inizio, fine)
        pezzi.append(testo[inizio:fine].strip())
        if fine >= len(testo):
            break
        prossimo = max(fine - sovrapposizione, inizio + 1)
        # la sovrapposizione riparte da inizio parola, non a metà
        spazio = testo.find(" ", prossimo, fine)
        inizio = spazio + 1 if spazio != -1 else prossimo
    return [p for p in pezzi if p]


def _taglio_naturale(testo: str, inizio: int, fine: int) -> int:
    """Cerca, negli ultimi 250 caratteri, una fine di frase; altrimenti uno spazio."""
    finestra_da = max(inizio + 1, fine - 250)
    migliore = -1
    for m in FINE_FRASE.finditer(testo, finestra_da, fine):
        migliore = m.end()
    if migliore > 0:
        return migliore
    spazio = testo.rfind(" ", finestra_da, fine)
    return spazio if spazio > 0 else fine
