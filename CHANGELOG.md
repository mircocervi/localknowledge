# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/). Versioni: [Semantic Versioning](https://semver.org/lang/it/).

## [1.0.0] - 2026-10-05

La prima versione pubblica.

### Aggiunto
- **Domande in italiano a una cartella di documenti**: PDF, Word, TXT, Markdown, CSV. Ogni affermazione porta documento e pagina.
- **OCR** delle pagine scansionate, con Tesseract o con un modello di visione locale.
- **Ricerca ibrida**: per parole (SQLite FTS5) e per significato (vettori calcolati sempre in locale con Ollama).
- **Tutto l'archivio o la ricerca**: se i documenti entrano nella memoria del modello li legge tutti, altrimenti legge le pagine più pertinenti.
- **Il controllo dopo la risposta**: citazioni inesistenti, frasi senza fonte, versioni diverse dello stesso documento.
- **Difesa dalle istruzioni nascoste** nei documenti, tolte prima che arrivino al modello.
- **Modelli locali o esterni**: Ollama, LM Studio, OpenRouter. Con OpenRouter una fascia rossa ricorda che gli estratti escono dal computer.
- **Server MCP** per Unsloth Studio, con gli strumenti `descrivi_archivio`, `cerca_nei_documenti` e `leggi_pagina`.

### Corretto
- Claude Opus su OpenRouter rispondeva con un errore quando il ragionamento era spento: ora la domanda si rifà con il ragionamento acceso, e la risposta lo dice.
