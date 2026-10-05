# Archivio (localknowledge)

App locale per fare domande a cartelle di documenti con citazioni documento+pagina. Usata in aula (corso "L'A.I. in casa", Alleniamo Imprese) sulla data-room fittizia di Crinale:
`~/projects/prv/formazione/alleniamoimprese/corso/dataset/data-room` (e `data-room-extra` con la trappola `99_..._TRAPPOLA.pdf`).

## Avvio e porte
- `uv run archivio.py` avvia tutto su **4100**: cliente `/`, admin `/admin`, MCP `/mcp/documenti`, MCP BI `/mcp/bi` (attivo solo se il modulo è acceso).
- `uv run server_mcp_documenti.py` è l'MCP autonomo su **4101**.
- Anteprima: `.claude/launch.json` → `archivio`.
- Test: `uv run archivio.py --prove`. Prova finale: `uv run archivio.py --prova-finale [--solo spark,minicpm] [--ragionamento]`.
- Dopo una modifica al Python l'app va riavviata (non c'è reload).

## Regole del progetto
- Lettura `auto` (`servizio.prepara`): se l'archivio entra nel contesto vero del modello (`modelli.contesto`), il modello legge tutto l'archivio; altrimenti si usa il RAG a pagine intere. LM Studio va caricato con `lms load -c 32768` (senza `--json`). Ollama via API OpenAI ignora `num_ctx`: MiniCPM5 resta a 4.096 token.
- La chiave OpenRouter sta in `.env` (fuori da git, permessi 600). Il modello preferito per fornitore è in `impostazioni.preferiti`.
- I vettori si calcolano **sempre** in locale (Ollama `qwen3-embedding:0.6b`), qualunque modello risponda.
- Un solo indice: `indice/archivio.db`. Il file è SQLite con FTS5 per le parole, mentre i vettori stanno come BLOB e in memoria come matrice numpy. Le impostazioni sono in `indice/impostazioni.json`, fuori da git.
- Gli originali non si toccano mai. Un pezzo non attraversa due pagine.
- La sicurezza non sta nel prompt:
  - `risposta._pulisci_estratto` toglie le frasi rivolte all'AI prima del modello;
  - `web.Guardia` blocca Host estranei e CSRF;
  - il server ascolta solo su 127.0.0.1.
- L'MCP segue lo stile di Crinale MCP (`corso/L05-chat-unica/mcp-unsloth/server_mcp_http.py`):
  - fastmcp 4;
  - strumenti con nomi italiani e docstring chiare per il modello;
  - output testuale, `ERRORE: …`.
- Il modulo BI è solo un segnaposto (`archivio_app/moduli.py`, `crea_mcp_bi`). Si costruirà sui dati di Crinale MCP (DuckDB, porta 5400).
- Il frontend è vanilla: niente build, niente CDN, font di sistema del Mac (Iowan Old Style, Avenir Next, SF Mono). Funziona offline.
- Le domande della prova finale stanno in `archivio_app/prova_finale.py`. Non mettere le risposte attese nel prompt del modello.

## Git
Repo privato `mircocervi/localknowledge`. Il lavoro si fa su `dev`, `main` è la produzione. Conventional Commits.
