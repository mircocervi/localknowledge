# /// script
# requires-python = ">=3.11"
# dependencies = ["fastmcp>=4,<5", "uvicorn", "httpx>=0.27", "numpy>=2"]
# ///
"""
Server MCP in HTTP sui documenti indicizzati da Archivio, per Unsloth Studio (e per chiunque parli MCP in HTTP).
È il gemello del server MCP di Crinale (DuckDB, porta 5400): stesso stile, così li colleghi insieme.

    uv run server_mcp_documenti.py                       http://127.0.0.1:4101/mcp
    uv run server_mcp_documenti.py --token segreto       chiede "Authorization: Bearer segreto"
    uv run server_mcp_documenti.py --porta 4102

Non serve se Archivio è già acceso: lo stesso MCP è anche su http://127.0.0.1:4100/mcp/documenti.

In Unsloth Studio: Add custom MCP, URL http://127.0.0.1:4101/mcp, autenticazione nessuna
(o Bearer con il token, se l'hai impostato).

Quattro strumenti: descrivi_archivio, cerca_nei_documenti, leggi_pagina, leggi_documento.
L'indice si costruisce dall'app (uv run archivio.py): questo server lo legge soltanto.
I vettori della domanda si calcolano in locale con Ollama (qwen3-embedding:0.6b); se Ollama è spento
la ricerca continua per sole parole.
"""
import argparse
import os
import socket
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)


class ControlloToken:
    """Middleware ASGI: senza il token giusto, 401."""
    def __init__(self, app, token: str):
        self.app, self.atteso = app, f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and dict(scope["headers"]).get(b"authorization") != self.atteso:
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"text/plain; charset=utf-8"), (b"www-authenticate", b"Bearer")]})
            await send({"type": "http.response.body", "body": "token mancante o sbagliato".encode()})
            return
        await self.app(scope, receive, send)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Server MCP in HTTP sui documenti di Archivio")
    p.add_argument("--porta", type=int, default=4101)
    p.add_argument("--token", default=os.environ.get("ARCHIVIO_MCP_TOKEN"), help="chiede Authorization: Bearer TOKEN")
    a = p.parse_args()

    with socket.socket() as prova:
        if prova.connect_ex(("127.0.0.1", a.porta)) == 0:
            sys.exit(f"La porta {a.porta} è già occupata: probabilmente il server è già acceso in un'altra finestra.\n"
                     f"Usa quello (http://127.0.0.1:{a.porta}/mcp), oppure fermalo con Ctrl+C, oppure scegli --porta {a.porta + 1}.")

    from archivio_app import config
    from archivio_app.indice import Indice
    from archivio_app.mcp_documenti import crea_mcp
    from archivio_app.servizio import Archivio

    if not config.FILE_DB.exists():
        sys.exit(f"Non trovo l'indice ({config.FILE_DB}). Avvia prima l'app: uv run archivio.py, e aggiungi una cartella.")
    mcp = crea_mcp(Archivio(Indice()))
    app = mcp.http_app(path="/mcp")
    if a.token:
        app = ControlloToken(app, a.token)
    print(f"Server MCP dei documenti su http://127.0.0.1:{a.porta}/mcp"
          f"{' (con token)' if a.token else ''}. Ctrl+C per fermarlo.", file=sys.stderr)
    import uvicorn
    # Solo 127.0.0.1: mai raggiungibile dalla rete.
    uvicorn.run(app, host="127.0.0.1", port=a.porta, log_level="warning")
