"""Dai file alle pagine di testo. Gli originali si aprono solo in lettura."""
import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

from . import ocr

MIN_CARATTERI_TESTO = 25  # sotto questa soglia di lettere/cifre la pagina è considerata scansionata
SEZIONE_TESTO = 3000      # TXT/MD non hanno pagine: li dividiamo in sezioni di circa 3.000 caratteri
RIGHE_CSV = 1000          # caratteri circa per blocco di righe CSV (con l'intestazione ripetuta)


@dataclass
class Pagina:
    numero: int
    testo: str
    ocr: bool = False


def pulisci(testo: str) -> str:
    testo = testo.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    testo = re.sub(r"[ \t ]+", " ", testo)
    testo = re.sub(r" *\n *", "\n", testo)
    testo = re.sub(r"\n{3,}", "\n\n", testo)
    return testo.strip()


def _ha_testo(testo: str) -> bool:
    return len(re.findall(r"\w", testo)) >= MIN_CARATTERI_TESTO


def estrai(percorso: Path, impostazioni: dict | None = None, avviso=None) -> tuple[str, list[Pagina]]:
    """Restituisce (tipo_unita, pagine). tipo_unita: 'pagina' o 'sezione'."""
    est = percorso.suffix.lower()
    if est == ".pdf":
        return "pagina", _pdf(percorso, impostazioni, avviso)
    if est == ".docx":
        return "pagina", _docx(percorso)
    if est == ".csv":
        return "sezione", _csv(percorso)
    if est in {".txt", ".md", ".markdown"}:
        return "sezione", _testo(percorso)
    raise ValueError(f"Formato non supportato: {est}")


def _pdf(percorso: Path, impostazioni, avviso) -> list[Pagina]:
    import pypdfium2 as pdfium

    pagine = []
    doc = pdfium.PdfDocument(str(percorso))
    try:
        for i in range(len(doc)):
            pag = doc[i]
            tp = pag.get_textpage()
            testo = tp.get_text_range()
            tp.close()
            usato_ocr = False
            if not _ha_testo(testo):
                if avviso:
                    avviso(f"OCR pagina {i + 1}")
                img = pag.render(scale=300 / 72).to_pil()
                testo = ocr.ocr_immagine(img, impostazioni)
                usato_ocr = True
            pag.close()
            pagine.append(Pagina(i + 1, pulisci(testo), usato_ocr))
    finally:
        doc.close()
    return pagine


def _docx(percorso: Path) -> list[Pagina]:
    """Word non salva le pagine: usiamo le interruzioni di pagina che Word registra quando salva."""
    import docx
    from docx.oxml.ns import qn

    d = docx.Document(str(percorso))
    pagine, corrente = [], []

    def chiudi():
        pagine.append(Pagina(len(pagine) + 1, pulisci("\n".join(corrente))))
        corrente.clear()

    corpo = d.element.body
    for blocco in corpo.iterchildren():
        if blocco.tag == qn("w:p"):
            riga = []
            for el in blocco.iter():
                if el.tag == qn("w:t") and el.text:
                    riga.append(el.text)
                elif el.tag == qn("w:tab"):
                    riga.append("\t")
                elif (el.tag == qn("w:br") and el.get(qn("w:type")) == "page") or el.tag == qn("w:lastRenderedPageBreak"):
                    if riga or corrente:
                        corrente.append("".join(riga))
                        riga = []
                        chiudi()
            corrente.append("".join(riga))
        elif blocco.tag == qn("w:tbl"):
            for tr in blocco.iter(qn("w:tr")):
                celle = ["".join(t.text or "" for t in tc.iter(qn("w:t"))) for tc in tr.iter(qn("w:tc"))]
                corrente.append(" | ".join(celle))
    chiudi()
    return [p for p in pagine if p.testo] or [Pagina(1, "")]


def leggi_testo(percorso: Path) -> str:
    grezzo = percorso.read_bytes()
    for codifica in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return grezzo.decode(codifica)
        except UnicodeDecodeError:
            continue
    return grezzo.decode("utf-8", "replace")


def _testo(percorso: Path) -> list[Pagina]:
    testo = leggi_testo(percorso)
    if "\f" in testo:  # interruzioni di pagina esplicite: le rispettiamo
        blocchi = testo.split("\f")
    else:
        blocchi, corrente = [], ""
        for riga in testo.splitlines(keepends=True):
            if len(corrente) + len(riga) > SEZIONE_TESTO and corrente:
                blocchi.append(corrente)
                corrente = ""
            corrente += riga
        blocchi.append(corrente)
    return [Pagina(i + 1, pulisci(b)) for i, b in enumerate(blocchi) if pulisci(b)] or [Pagina(1, "")]


def _csv(percorso: Path) -> list[Pagina]:
    """Ogni blocco di righe porta con sé l'intestazione: un pezzo di CSV senza colonne non si capisce."""
    testo = leggi_testo(percorso)
    try:
        dialetto = csv.Sniffer().sniff(testo[:4096], delimiters=",;\t|")
    except csv.Error:
        dialetto = csv.excel
    righe = list(csv.reader(io.StringIO(testo), dialetto))
    if not righe:
        return [Pagina(1, "")]
    intestazione, dati = righe[0], righe[1:]
    pagine, blocco, lunghezza = [], [], 0
    for r in dati:
        riga = "; ".join(f"{c}: {v}" for c, v in zip(intestazione, r) if v != "")
        if lunghezza + len(riga) > RIGHE_CSV and blocco:
            pagine.append(blocco)
            blocco, lunghezza = [], 0
        blocco.append(riga)
        lunghezza += len(riga) + 1
    if blocco:
        pagine.append(blocco)
    testa = "Colonne: " + ", ".join(intestazione)
    return [Pagina(i + 1, testa + "\n" + "\n".join(b)) for i, b in enumerate(pagine)] or [Pagina(1, testa)]
