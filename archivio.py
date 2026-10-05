# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fastapi>=0.115",
#   "uvicorn>=0.30",
#   "fastmcp>=4,<5",
#   "httpx>=0.27",
#   "numpy>=2",
#   "pypdfium2>=4.30",
#   "pillow>=10",
#   "python-docx>=1.1",
#   "watchdog>=5",
#   "pytest>=8",
# ]
# ///
"""
Archivio: fai domande a una cartella di documenti, tutto in locale.

    uv run archivio.py                 apre http://127.0.0.1:4100 (cliente) e /admin
    uv run archivio.py --no-browser    senza aprire il browser
    uv run archivio.py --prove         esegue i test automatici
    uv run archivio.py --prova-finale  le 3 domande della data-room su ogni modello acceso

MCP in HTTP per Unsloth Studio (Add custom MCP): http://127.0.0.1:4100/mcp/documenti
"""
import argparse
import os
import sys
import threading
import webbrowser

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)


def main() -> None:
    p = argparse.ArgumentParser(description="Archivio: domande ai tuoi documenti, in locale.")
    p.add_argument("--porta", type=int, default=4100)
    p.add_argument("--no-browser", action="store_true", help="non aprire il browser all'avvio")
    p.add_argument("--prove", action="store_true", help="esegue i test automatici e esce")
    p.add_argument("--prova-finale", action="store_true", help="prova le 3 domande su ogni modello acceso")
    a, _ = p.parse_known_args()  # --solo e --ragionamento li legge la prova finale

    if a.prove:
        import pytest
        sys.exit(pytest.main(["-q", os.path.join(QUI, "prove")]))
    if a.prova_finale:
        from archivio_app.prova_finale import main as prova
        sys.exit(prova())

    import uvicorn
    from archivio_app.web import crea_app

    url = f"http://127.0.0.1:{a.porta}"
    print(f"\n  Archivio          {url}\n  Area admin        {url}/admin\n"
          f"  MCP documenti     {url}/mcp/documenti\n\n  Ctrl+C per fermare.\n")
    if not a.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    # Solo 127.0.0.1: l'app non è mai raggiungibile dalla rete.
    uvicorn.run(crea_app(), host="127.0.0.1", port=a.porta, log_level="warning")


if __name__ == "__main__":
    main()
