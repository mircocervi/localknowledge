# Archivio

Fai domande in italiano a una cartella di documenti. Le risposte arrivano **solo** dai documenti, con documento e pagina per ogni affermazione. Tutto gira su questo computer.

**[La pagina di presentazione](https://mircocervi.github.io/localknowledge/)** · [Licenza](LICENSE.md) · [Novità](CHANGELOG.md)

## Per cominciare

Provato su Mac con Apple Silicon. Servono tre cose, da installare una volta sola.

1. **uv**, che prepara le librerie e avvia l'app:
   ```bash
   brew install uv
   ```
   Senza Homebrew: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
2. **[Ollama](https://ollama.com/download)**, con il modello dei vettori e un modello che risponde:
   ```bash
   ollama pull qwen3-embedding:0.6b
   ollama pull hf.co/XHToken/Spark-X2.5-4B-GGUF:Q8_0
   ```
3. **Tesseract**, solo se hai PDF scansionati:
   ```bash
   brew install tesseract tesseract-lang
   ```

Poi scarica il progetto (da GitHub, **Code → Download ZIP**, oppure `git clone https://github.com/mircocervi/localknowledge.git`) e dalla sua cartella:

```bash
uv run archivio.py
```

Si apre `http://127.0.0.1:4100`. Al primo avvio uv scarica le librerie, e ci vuole qualche minuto. Dall'area admin, su `/admin`, scegli la cartella dei documenti: i tuoi, o quella del corso.

## Cosa fa

1. **Cartelle.** Ne scegli una o più (PDF, Word `.docx`, TXT, Markdown, CSV). Gli originali si aprono solo in lettura.
2. **Indicizza.** Estrae il testo pagina per pagina e fa l'OCR in italiano sulle pagine scansionate (Tesseract, oppure un modello di visione locale). Poi taglia il testo in pezzi di circa 1.000 caratteri sovrapposti di 150, e ogni pezzo ricorda documento e pagina.
3. **Cerca.** La ricerca è ibrida:
   - per parole (SQLite FTS5, BM25, con un vocabolario di sinonimi) trova codici, importi, nomi e articoli;
   - per significato (vettori `qwen3-embedding:0.6b`, sempre calcolati in locale con Ollama) trova lo stesso concetto detto con altre parole;
   - le due classifiche si fondono con la Reciprocal Rank Fusion.
4. **Sceglie cosa far leggere al modello.** Se l'archivio entra nella memoria di lavoro (il contesto) del modello, gli fa leggere **tutto l'archivio**, pagina per pagina. È il caso della data-room di Crinale con Spark. Se non entra, usa la **ricerca (RAG)** e passa le pagine intere più pertinenti, quante ne stanno. Il contesto reale lo legge da Ollama o LM Studio, che viene caricato con 32k.
5. **Risponde.** Il modello cita gli estratti `[E1]`, `[E2]`, che diventano etichette cliccabili con documento e pagina. Se l'informazione manca, risponde «Non presente nei documenti».
6. **Controlla.** Dopo la risposta l'app verifica che:
   - ogni citazione esista davvero;
   - non ci siano frasi senza fonte;
   - siano segnalate le versioni dello stesso documento (es. `Contratto_Nordwand_2016` → `Rinnovo_Nordwand_2024`), indicando la più recente.
7. **Si difende.** Toglie dagli estratti le frasi che danno ordini a un'AI prima che arrivino al modello, e le mostra come «istruzioni nascoste ignorate».
8. **Si aggiorna da sola.** Quando aggiungi, cambi o togli un file nella cartella, reindicizza solo quel file.

**Freno:**
- **Ferma** interrompe la risposta in corso.
- **Spegni il motore** toglie tutti i modelli dalla memoria di Ollama e LM Studio, per far raffreddare il Mac.

## Modelli

Per tutti usa la stessa API compatibile OpenAI: cambiano solo l'indirizzo e il modello.

| Da dove | Indirizzo | Note |
|---|---|---|
| Ollama | `http://localhost:11434/v1` | qui stanno anche i vettori |
| LM Studio | `http://localhost:1234/v1` | |
| OpenRouter | `https://openrouter.ai/api/v1` | chiave in `OPENROUTER_API_KEY` (o in un file `.env`, fuori da git). Una fascia rossa ricorda che **gli estratti escono dal computer**. |

Modelli provati: Spark X2.5 4B (`ollama pull hf.co/XHToken/Spark-X2.5-4B-GGUF:Q8_0`), MiniCPM5 2B, Qwen.

## MCP (per Unsloth Studio)

Lo stile è lo stesso del server MCP di Crinale (DuckDB, porta 5400), così li colleghi insieme. In Unsloth Studio: *Add custom MCP* → URL → autenticazione nessuna.

| Server | URL |
|---|---|
| Documenti (con l'app accesa) | `http://127.0.0.1:4100/mcp/documenti` |
| Documenti (da solo: `uv run server_mcp_documenti.py`) | `http://127.0.0.1:4101/mcp` |
| BI (modulo, si accende da /admin → Moduli) | `http://127.0.0.1:4100/mcp/bi` |

Gli strumenti sono `descrivi_archivio`, `cerca_nei_documenti` e `leggi_pagina`.

## Comandi

```bash
uv run archivio.py                    # l'app (cliente + admin + MCP)
uv run archivio.py --prova-finale     # 3 domande della data-room su ogni modello acceso
uv run archivio.py --prove            # test automatici
uv run server_mcp_documenti.py        # solo l'MCP, porta 4101
```

## Dove stanno le cose

- `archivio.py`: il punto d'avvio, con le dipendenze dichiarate in testa (uv);
- `archivio_app/`: il motore:
  - `estrazione` e `ocr` per leggere i file;
  - `pezzi` per tagliare il testo;
  - `vettori` per i calcoli di significato;
  - `indice` per l'archivio SQLite e la ricerca ibrida;
  - `risposta` per prompt e verifica;
  - `versioni`, `mcp_documenti`, `moduli`;
  - `web` per il server;
- `web/`: le pagine del cliente e dell'admin, senza build e senza CDN, quindi funzionano anche offline;
- `indice/`: l'indice (`archivio.db`), le impostazioni e i risultati del banco prova. È fuori da git: se lo cancelli, si ricostruisce.
- `prove/`: i test.

Sicurezza:
- il server ascolta solo su `127.0.0.1`;
- rifiuta le richieste con un Host estraneo (DNS rebinding) e quelle che modificano qualcosa arrivando da altri siti (CSRF).

## Licenza

Gratis per lo studio, l'insegnamento e ogni uso non commerciale, con la [PolyForm Noncommercial 1.0.0](LICENSE.md). Per usarlo in un'azienda o in uno studio professionale serve una licenza scritta, anche questa gratuita: [come si chiede](COMMERCIAL.md). I componenti scritti da altri sono in [NOTICE.md](NOTICE.md).

Archivio è di [Mirco Cervi](https://mircocervi.it).
