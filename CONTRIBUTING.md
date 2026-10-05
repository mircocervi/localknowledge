# Contribuire

Grazie se vuoi migliorare Archivio. Due cose da sapere prima di aprire una pull request.

## L'accordo per chi contribuisce

Archivio ha due licenze: gratis per lo studio e l'uso non commerciale, e una licenza scritta, sempre gratuita, per le aziende. Per tenerle in piedi entrambe, ogni contributo deve poter essere distribuito con tutte e due. È quello che fa il [Contributor Licence Agreement](CLA.md): il tuo lavoro resta tuo, e permetti che entri in entrambe le versioni.

Per accettarlo basta una riga nella pull request, come nel modello.

## Per partire

Serve [uv](https://docs.astral.sh/uv/). Le dipendenze sono dichiarate in testa ad `archivio.py`.

```bash
uv run archivio.py --prove            # i test
uv run archivio.py                    # l'app, su http://127.0.0.1:4100
```

## Come è scritto il codice

- **Commenti e messaggi in italiano.** È voluto: il progetto nasce per un corso italiano, per persone che non programmano.
- **I commit seguono [Conventional Commits](https://www.conventionalcommits.org/)**: `feat:`, `fix:`, `docs:`, `test:`.
- **Ogni bug corretto lascia un test** in `prove/`, con un commento che dice quale comportamento sbagliato impedisce.
- **La sicurezza non sta nel prompt.** Le difese sono nel codice: `risposta._pulisci_estratto`, `web.Guardia`, il server solo su `127.0.0.1`.
- **Il frontend resta senza build e senza CDN.** Deve funzionare offline, in un'aula senza rete.

## I dati

Negli issue, nei test e nelle pull request usa solo documenti inventati. Mai documenti veri, nemmeno «solo per far vedere il problema».
