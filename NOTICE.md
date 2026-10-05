# Componenti di terzi

Archivio è scritto da Mirco Cervi. Gira su componenti scritti da altri, ognuno con la sua licenza, che la [licenza di Archivio](LICENSE.md) non cambia. Nessuno di questi è copiato nel repository: `uv` li scarica al primo avvio.

## Le librerie

| Componente | Licenza | A cosa serve |
|---|---|---|
| FastAPI, Starlette | MIT | il server dell'app |
| Uvicorn | BSD-3-Clause | il server dell'app |
| FastMCP | Apache-2.0 | i server MCP |
| HTTPX | BSD-3-Clause | le chiamate a Ollama, LM Studio, OpenRouter |
| NumPy | BSD-3-Clause | i vettori di significato |
| pypdfium2, con PDFium | Apache-2.0 o BSD-3-Clause | leggere e disegnare le pagine dei PDF |
| Pillow | MIT-CMU | le immagini delle pagine |
| python-docx | MIT | i file Word |
| watchdog | Apache-2.0 | accorgersi dei file nuovi o cambiati |
| pytest | MIT | i test |

## Installati a parte

| Componente | Licenza | Note |
|---|---|---|
| [uv](https://github.com/astral-sh/uv) | MIT o Apache-2.0 | avvia l'app e prepara le librerie |
| [Ollama](https://github.com/ollama/ollama) | MIT | modelli locali e vettori |
| [LM Studio](https://lmstudio.ai) | licenza propria, gratuita | modelli locali, facoltativo |
| [Tesseract](https://github.com/tesseract-ocr/tesseract) | Apache-2.0 | OCR delle pagine scansionate, facoltativo |

## I modelli

I modelli non sono nel repository: li scarichi tu, con Ollama o LM Studio, e ognuno ha la sua licenza. Leggila prima di usarlo per lavoro.

| Modello | Licenza | Uso |
|---|---|---|
| [qwen3-embedding:0.6b](https://ollama.com/library/qwen3-embedding) | Apache-2.0 | i vettori di significato, sempre in locale |

Con OpenRouter valgono anche le condizioni di OpenRouter e del fornitore del modello scelto. In quel caso gli estratti dei documenti escono dal computer, e l'app lo dice con una fascia rossa.
