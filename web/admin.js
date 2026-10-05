// Archivio — area admin. Una sezione per voce dell'indice, scelta dall'#ancora.

$$("[data-icona]").forEach(el => (el.outerHTML = icona(el.dataset.icona)));
const C = $("#contenuto");
const A = { stato: null, registro: [], dopo: 0, timerProva: null };

function testata(num, titolo, sotto, destra = "") {
  return `<header><div style="flex:1;min-width:280px"><div class="num">${num}</div><h1>${titolo}</h1>${sotto ? `<p>${sotto}</p>` : ""}</div>${destra}</header>`;
}
function errore(e) { return `<div class="nota errore">${icona("avviso")}<div>${esc(e.message || e)}</div></div>`; }
function comp({ titolo, stato = "neutro", ver = "", serve = "", dett = [], extra = "" }) {
  const p = stato === "acceso" ? "acceso" : stato === "spento" ? "spento" : "";
  return `<div class="carta comp ${stato === "spento" ? "spento" : ""}">
    <div class="testa"><span class="pallino ${p}"></span><h3>${titolo}</h3></div>
    ${ver ? `<div class="ver">${ver}</div>` : ""}
    <p class="serve">${serve}</p>${extra}
    ${dett.length ? `<div class="dett">${dett.map(([k, v]) => `<div><span>${k}</span><span class="mono">${v}</span></div>`).join("")}</div>` : ""}
  </div>`;
}

// ============ I. Il sistema ============
async function sezSistema() {
  C.innerHTML = `<section class="sezione">${testata("I · Scheda per l'aula", "Cosa c'è installato su questo Mac",
    "Tutto quello che serve ad Archivio, verificato dal vivo adesso. Niente gira su server esterni, a meno che non scegli OpenRouter.",
    `<button class="btn no-stampa" onclick="print()">${icona("stampa")} Stampa la scheda</button>`)}
    <div id="sis"><p class="piccolo">Controllo i componenti<span class="puntini"></span></p></div></section>`;
  let s;
  try { s = await api("/api/sistema"); } catch (e) { $("#sis").innerHTML = errore(e); return; }
  const oll = s.ollama, lms = s.lmstudio, tes = s.tesseract;
  const dimVett = A.stato?.totale?.dimensioni_vettore || 1024;
  $("#sis").innerHTML = `
    <p class="stampa-solo piccolo">Scheda generata il ${new Date().toLocaleString("it-IT")}</p>
    <div class="griglia">
      ${comp({ titolo: "Questo Mac", stato: "acceso", ver: esc(s.mac.sistema), serve: "Qui stanno documenti, indice e vettori. Con Ollama o LM Studio anche il modello che risponde.",
        dett: [["Processore", esc(s.mac.chip)], ["Memoria", s.mac.ram_gb ? s.mac.ram_gb + " GB" : "?"]] })}
      ${comp({ titolo: "Archivio", stato: "acceso", ver: "versione " + esc(s.app.versione), serve: "Questa app: indicizza le cartelle, cerca, fa rispondere il modello e controlla le citazioni. Ascolta solo su 127.0.0.1.",
        dett: [["Cliente", esc(s.app.url)], ["Admin", esc(s.app.admin)], ["MCP", esc(s.app.mcp)]] })}
      ${comp({ titolo: "Python e uv", stato: s.python.uv ? "acceso" : "neutro", ver: `Python ${esc(s.python.versione)} · uv ${esc(s.python.uv || "?")}`,
        serve: "uv legge le dipendenze scritte in cima ad archivio.py e prepara tutto da solo: si parte con un solo comando.",
        dett: [["Avvio", "uv run archivio.py"]] })}
      ${comp({ titolo: "Ollama", stato: oll.acceso ? "acceso" : "spento", ver: oll.acceso ? "versione " + esc(oll.versione) : "non risponde",
        serve: "Calcola i vettori, sempre e solo in locale. Può anche far rispondere i modelli (Spark, MiniCPM…).",
        dett: [["Indirizzo", "localhost:11434/v1"], ["Modelli", oll.modelli.length], ["In memoria", oll.modelli.filter(m => m.in_memoria).length]] })}
      ${comp({ titolo: "LM Studio", stato: lms.acceso ? "acceso" : "spento", ver: lms.acceso ? `${lms.modelli.length} modelli` : "server spento",
        serve: "Un'altra casa per i modelli locali, con un'interfaccia grafica. Stessa API compatibile OpenAI.",
        dett: [["Indirizzo", "localhost:1234/v1"], ["Caricati ora", lms.modelli.filter(m => m.caricato).length]] })}
      ${comp({ titolo: "OpenRouter", stato: s.openrouter.chiave ? "acceso" : "neutro", ver: s.openrouter.chiave ? "chiave presente" : "nessuna chiave",
        serve: "Modelli in cloud, solo per prova. <b>Gli estratti dei documenti escono dal computer.</b> La chiave sta nella variabile OPENROUTER_API_KEY, mai nel codice.",
        dett: [["Indirizzo", "openrouter.ai/api/v1"]] })}
      ${comp({ titolo: "Modello dei vettori", stato: s.embedding.presente ? "acceso" : "spento", ver: esc(s.embedding.modello),
        serve: `Trasforma ogni pezzo di testo in ${numero(dimVett)} numeri che ne rappresentano il significato. Gira in Ollama, qualunque modello risponda.`,
        dett: [["Dove", esc(s.embedding.dove)], ["Dimensioni", numero(dimVett)]] })}
      ${comp({ titolo: "Tesseract OCR", stato: tes.installato ? "acceso" : "spento", ver: tes.installato ? "versione " + esc(tes.versione) : "non installato",
        serve: "Legge le pagine scansionate, quelle senza testo selezionabile. Usa il dizionario italiano.",
        dett: [["Italiano", tes.italiano ? "sì" : "no"], ["Lingue", tes.lingue || 0], ["Motore scelto", esc(s.ocr.motore === "visione" ? "modello di visione · " + s.ocr.modello : "Tesseract")]] })}
      ${comp({ titolo: "SQLite + FTS5", stato: s.sqlite.fts5 ? "acceso" : "spento", ver: "versione " + esc(s.sqlite.versione),
        serve: "L'indice è un solo file: testo, pezzi, vettori e l'indice per parole (BM25). Incluso in Python, zero server.",
        dett: [["File", "indice/archivio.db"]] })}
    </div>

    <h2 class="sotto">I modelli installati</h2>
    <div class="carta tabella-box"><table class="tabella">
      <thead><tr><th>Dove</th><th>Modello</th><th>Uso</th><th>Dettagli</th><th class="num">Dimensione</th><th>Stato</th></tr></thead>
      <tbody>${[
        ...oll.modelli.map(m => `<tr><td>Ollama</td><td class="mono">${esc(m.nome)}</td><td>${m.embedding ? "vettori" : "risponde"}</td>
          <td class="piccolo">${esc(m.parametri || "")}</td><td class="num">${m.gb} GB</td><td>${m.in_memoria ? '<span class="tag ok">in memoria</span>' : '<span class="piccolo">pronto</span>'}</td></tr>`),
        ...lms.modelli.map(m => `<tr><td>LM Studio</td><td class="mono">${esc(m.nome)}</td><td>${m.tipo === "embeddings" ? "vettori" : m.tipo === "vlm" ? "risponde · vede immagini" : "risponde"}</td>
          <td class="piccolo">${esc([m.quantizzazione, m.contesto ? Math.round(m.contesto / 1000) + "k contesto" : ""].filter(Boolean).join(" · "))}</td><td class="num">—</td>
          <td>${m.caricato ? '<span class="tag ok">caricato</span>' : '<span class="piccolo">su disco</span>'}</td></tr>`),
      ].join("") || '<tr><td colspan="6" class="piccolo">Nessun server di modelli acceso.</td></tr>'}</tbody></table></div>

    <h2 class="sotto">Le librerie Python</h2>
    <div class="carta tabella-box"><table class="tabella">
      <thead><tr><th>Libreria</th><th>Versione</th><th>A cosa serve qui</th><th>Licenza</th></tr></thead>
      <tbody>${s.librerie.map(l => `<tr><td class="mono">${esc(l.nome)}</td><td class="mono">${esc(l.versione || "—")}</td><td>${esc(l.ruolo)}</td><td class="piccolo">${esc(l.licenza)}</td></tr>`).join("")}</tbody></table></div>

    <h2 class="sotto">Gli indirizzi</h2>
    <div class="carta tabella-box"><table class="tabella"><thead><tr><th>Cosa</th><th>Indirizzo</th><th>Note</th></tr></thead><tbody>
      <tr><td>Archivio · cliente</td><td class="mono">http://127.0.0.1:4100</td><td class="piccolo">quello che vede chi fa le domande</td></tr>
      <tr><td>Archivio · admin</td><td class="mono">http://127.0.0.1:4100/admin</td><td class="piccolo">questa pagina</td></tr>
      <tr><td>MCP documenti</td><td class="mono">http://127.0.0.1:4100/mcp/documenti</td><td class="piccolo">per Unsloth Studio, acceso con l'app</td></tr>
      <tr><td>MCP documenti (autonomo)</td><td class="mono">http://127.0.0.1:4101/mcp</td><td class="piccolo">uv run server_mcp_documenti.py</td></tr>
      <tr><td>MCP Crinale (DuckDB)</td><td class="mono">http://127.0.0.1:5400/mcp</td><td class="piccolo">i numeri di Crinale, base della BI</td></tr>
      <tr><td>Ollama</td><td class="mono">http://localhost:11434/v1</td><td class="piccolo">API compatibile OpenAI</td></tr>
      <tr><td>LM Studio</td><td class="mono">http://localhost:1234/v1</td><td class="piccolo">API compatibile OpenAI</td></tr>
      <tr><td>OpenRouter</td><td class="mono">https://openrouter.ai/api/v1</td><td class="piccolo">fuori dal computer</td></tr>
    </tbody></table></div>

    <h2 class="sotto">I comandi</h2>
    <pre class="prompt">uv run archivio.py                      # avvia l'app e apre il browser
uv run archivio.py --prova-finale       # le 3 domande su ogni modello acceso
uv run archivio.py --prove              # i test automatici
uv run server_mcp_documenti.py          # MCP dei documenti da solo, porta 4101
ollama pull qwen3-embedding:0.6b        # il modello dei vettori
ollama pull hf.co/XHToken/Spark-X2.5-4B-GGUF:Q8_0   # Spark X2.5 4B</pre>`;
}

// ============ II. Come funziona ============
function diagramma() {
  const box = (x, y, w, t1, t2, col = "var(--inchiostro)") => `
    <g><rect x="${x}" y="${y}" width="${w}" height="64" rx="4" fill="var(--foglio)" stroke="${col}" stroke-width="1.3"/>
    <text x="${x + w / 2}" y="${y + 27}" text-anchor="middle" font-size="14" font-weight="600">${t1}</text>
    <text x="${x + w / 2}" y="${y + 46}" text-anchor="middle" font-size="11.5" style="fill:var(--grigio)">${t2}</text></g>`;
  const fr = (x1, y1, x2, y2) => `<path d="M${x1} ${y1} C ${(x1 + x2) / 2} ${y1}, ${(x1 + x2) / 2} ${y2}, ${x2} ${y2}" fill="none" stroke="var(--linea-forte)" stroke-width="1.5" marker-end="url(#punta)"/>`;
  return `<svg viewBox="0 0 1100 230" role="img" aria-label="Il percorso di un documento e di una domanda">
    <defs><marker id="punta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 10 5 0 10z" fill="var(--linea-forte)"/></marker></defs>
    <text x="0" y="14" font-size="10.5" style="fill:var(--timbro);font-family:var(--f-mono);letter-spacing:.15em">UNA VOLTA, QUANDO ARRIVA UN DOCUMENTO</text>
    <text x="700" y="226" font-size="10.5" style="fill:var(--timbro);font-family:var(--f-mono);letter-spacing:.15em">A OGNI DOMANDA</text>
    ${box(0, 40, 120, "Cartella", "PDF · Word · testo")}
    ${box(150, 40, 140, "Estrazione", "testo o OCR")}
    ${box(320, 40, 140, "Pezzi", "1.000 car. sovrapposti")}
    ${box(500, 0 + 22, 160, "Indice per parole", "SQLite FTS5 · BM25", "var(--ocra)")}
    ${box(500, 96, 160, "Vettori", "qwen3-embedding, locale", "var(--verderame)")}
    ${box(700, 140, 140, "Domanda", "in italiano")}
    ${box(700, 40, 140, "Ricerca ibrida", "fusione RRF · top 8", "var(--timbro)")}
    ${box(870, 40, 110, "Modello", "Ollama · LM Studio")}
    ${box(1000, 40, 100, "Risposta", "citazioni verificate", "var(--timbro)")}
    ${fr(120, 72, 150, 72)}${fr(290, 72, 320, 72)}${fr(460, 72, 500, 54)}${fr(460, 72, 500, 128)}
    ${fr(660, 54, 700, 66)}${fr(660, 128, 700, 80)}${fr(770, 140, 770, 106)}${fr(840, 72, 870, 72)}${fr(980, 72, 1000, 72)}
  </svg>`;
}

async function sezCome() {
  C.innerHTML = `<section class="sezione">${testata("III · Per la lezione", "Come funziona, passo per passo",
    "Dal file sul disco alla risposta con la citazione. Ogni riquadro è un pezzo del programma che si può aprire e guardare.")}
    <div class="carta filiera">${diagramma()}</div>
    <div class="passi">
      <div class="carta passo"><h3><i>1</i> Estrazione</h3><p>Il testo si legge pagina per pagina. Se una pagina non ha testo selezionabile è una scansione: la si trasforma in immagine e la legge l'OCR (Tesseract, in italiano).</p></div>
      <div class="carta passo"><h3><i>2</i> Pezzi</h3><p>Ogni pagina si taglia in pezzi di circa 1.000 caratteri, che si sovrappongono di 150 per non spezzare una frase a metà. Ogni pezzo ricorda documento e pagina: è quello che si cita.</p></div>
      <div class="carta passo"><h3><i>3</i> Parole</h3><p>L'indice per parole trova codici, importi, nomi e numeri d'articolo esatti ("MAG02", "14.3"). Un vocabolario di sinonimi aiuta: chi chiede "cause" trova anche "ricorso" e "tribunale".</p></div>
      <div class="carta passo"><h3><i>4</i> Significato</h3><p>I vettori trovano i pezzi che dicono la stessa cosa con parole diverse ("disdetta" e "recesso"). Si calcolano sempre in locale, anche quando risponde un modello in cloud.</p></div>
      <div class="carta passo"><h3><i>5</i> Fusione</h3><p>Le due classifiche si fondono con la Reciprocal Rank Fusion: ogni pezzo prende 1/(60 + posizione) da ciascuna. Vince chi è in alto in tutte e due. Ai modelli arrivano gli 8 migliori.</p></div>
      <div class="carta passo"><h3><i>6</i> Risposta e verifica</h3><p>Il modello risponde solo con gli estratti e cita [E1], [E2]. L'app controlla che ogni citazione esista davvero, segnala le frasi senza fonte e le versioni dello stesso documento.</p></div>
    </div>

    <h2 class="sotto">Cosa sono i vettori</h2>
    <p style="max-width:72ch;margin-top:0">Un vettore è una lista di ${numero(A.stato?.totale?.dimensioni_vettore || 1024)} numeri che descrive il <b>significato</b> di un testo.
      Due frasi che dicono la stessa cosa hanno vettori vicini, anche senza nessuna parola in comune. La vicinanza si misura da 0 (niente a che vedere) a 1 (stesso significato).
      Prova: cambia le frasi e ricalcola.</p>
    <div class="carta lab-vettori">
      <div>
        ${["Il contratto si può disdire con trenta giorni di preavviso.", "È possibile recedere dall'accordo con un mese di anticipo.", "Le vendite in Germania sono cresciute del 12%.", "La ricetta del tiramisù vuole il mascarpone."]
          .map((f, i) => `<input class="campo frase" style="margin-bottom:8px" value="${esc(f)}" aria-label="Frase ${i + 1}">`).join("")}
        <button class="btn pieno" id="calcola">${icona("chip")} Calcola i vettori</button>
      </div>
      <div id="esito-vettori" class="piccolo">I vettori li calcola Ollama, qui sul Mac.</div>
    </div>

    <h2 class="sotto">Perché una ricerca ibrida</h2>
    <div class="carta tabella-box"><table class="tabella"><thead><tr><th>Domanda</th><th>Per parole</th><th>Per significato</th></tr></thead><tbody>
      <tr><td>«Cosa dice il contratto MAG02?»</td><td><span class="tag ok">trova</span> il codice esatto</td><td><span class="tag no">fatica</span> un codice non ha "significato"</td></tr>
      <tr><td>«Si può disdire l'accordo?»</td><td><span class="tag no">fatica</span> il testo dice "recesso"</td><td><span class="tag ok">trova</span> stesso concetto</td></tr>
      <tr><td>«Art. 14.3»</td><td><span class="tag ok">trova</span> la frase esatta</td><td><span class="tag neutro">a caso</span></td></tr>
      <tr><td>«Ci sono cause in corso?»</td><td><span class="tag ok">trova</span> con i sinonimi: ricorso, tribunale</td><td><span class="tag neutro">dipende</span> un modello piccolo distingue poco</td></tr>
    </tbody></table></div>

    <h2 class="sotto">Le regole date al modello</h2>
    <div id="regole"><p class="piccolo">Carico<span class="puntini"></span></p></div>

    <h2 class="sotto">Le difese</h2>
    <div class="passi">
      <div class="carta passo"><h3>${icona("lucchetto")} Solo su questo Mac</h3><p>Il server ascolta su 127.0.0.1: dalla rete non si raggiunge. Le richieste con un Host estraneo o arrivate da altri siti vengono rifiutate.</p></div>
      <div class="carta passo"><h3>${icona("doc")} Originali intatti</h3><p>I documenti si aprono solo in lettura. L'indice sta nella cartella <span class="mono">indice/</span> accanto all'app: se lo cancelli, si ricostruisce.</p></div>
      <div class="carta passo"><h3>${icona("avviso")} Dati, non istruzioni</h3><p>Gli estratti arrivano al modello chiusi tra delimitatori. Se un documento contiene ordini rivolti all'AI, il modello deve ignorarli, e i delimitatori non si possono chiudere dall'interno.</p></div>
      <div class="carta passo"><h3>${icona("uscita")} Avviso fisso</h3><p>Con OpenRouter una fascia rossa resta sempre in vista: gli estratti escono dal computer. I vettori invece restano comunque in locale.</p></div>
    </div>
  </section>`;
  $("#calcola").addEventListener("click", calcolaVettori);
  calcolaVettori();
  try {
    const r = await api("/api/laboratorio/cerca", { metodo: "POST", dati: { domanda: A.stato?.domande_esempio?.[0] || "contratto" } });
    $("#regole").innerHTML = `<pre class="prompt">${esc(r.messaggi[0].content)}</pre>`;
  } catch (e) { $("#regole").innerHTML = errore(e); }
}

async function calcolaVettori() {
  const frasi = $$(".frase").map(i => i.value.trim()).filter(Boolean);
  const out = $("#esito-vettori");
  out.innerHTML = `Calcolo<span class="puntini"></span>`;
  try {
    const r = await api("/api/laboratorio/vettori", { metodo: "POST", dati: { frasi } });
    const n = r.frasi.length;
    const cella = v => `<div style="background:color-mix(in srgb, var(--verderame) ${Math.max(0, Math.round((v - .2) / .8 * 100))}%, var(--foglio-2));color:${v > .62 ? "var(--foglio)" : "var(--inchiostro)"}">${v.toFixed(2).replace(".", ",")}</div>`;
    out.innerHTML = `
      <div class="matrice" style="grid-template-columns: 1.6fr repeat(${n}, 1fr)">
        <div class="et"></div>${r.frasi.map((_, i) => `<div class="et" style="text-align:center">F${i + 1}</div>`).join("")}
        ${r.similarita.map((riga, i) => `<div class="et" title="${esc(r.frasi[i])}">F${i + 1} · ${esc(r.frasi[i])}</div>${riga.map(cella).join("")}`).join("")}
      </div>
      <p style="margin:14px 0 6px"><b>F1 in numeri</b> (i primi 16 di ${numero(r.dimensioni)}):</p>
      <div class="numeri">[${r.anteprima[0].map(x => x.toFixed(3)).join(", ")}, …]</div>
      <p class="piccolo" style="margin-top:10px">Modello: <span class="mono">${esc(r.modello)}</span>. F1 e F2 non hanno parole in comune ma sono vicine: è questo che i vettori aggiungono alla ricerca per parole.</p>`;
  } catch (e) { out.innerHTML = errore(e); }
}

// ============ III. Indice ============
async function sezIndice() {
  const st = A.stato;
  C.innerHTML = `<section class="sezione">${testata("IV · L'indice", "Cosa ha letto l'app",
    "Ogni documento, pagina per pagina, con i pezzi e i loro vettori. Clicca un documento per aprirlo.",
    `<div class="no-stampa" style="display:flex;gap:8px"><button class="btn" id="vettori-mancanti">${icona("chip")} Completa vettori</button></div>`)}
    <div class="tessere">
      <div class="carta tessera"><b>${numero(st.totale.documenti)}</b><span>documenti</span></div>
      <div class="carta tessera"><b>${numero(st.totale.pagine)}</b><span>pagine</span></div>
      <div class="carta tessera"><b>${numero(st.totale.pagine_ocr)}</b><span>pagine con OCR</span></div>
      <div class="carta tessera"><b>${numero(st.totale.pezzi)}</b><span>pezzi</span></div>
      <div class="carta tessera"><b>${numero(st.totale.con_vettore)}</b><span>vettori da ${numero(st.totale.dimensioni_vettore)} numeri</span></div>
      <div class="carta tessera"><b>${byte(st.totale.byte)}</b><span>file dell'indice</span></div>
    </div>
    <div id="cartelle-admin"></div></section>`;
  $("#vettori-mancanti").onclick = async () => { await api("/api/vettori/completa", { metodo: "POST" }); biglietto(`${icona("chip")}<div><b>Controllo i vettori mancanti</b></div>`); };
  const box = $("#cartelle-admin");
  if (!st.cartelle.length) { box.innerHTML = `<div class="nota">${icona("cartella")}<div>Nessuna cartella: aggiungila dalla <a href="/">vista cliente</a>.</div></div>`; return; }
  const docs = await api("/api/documenti");
  box.innerHTML = st.cartelle.map(c => {
    const d = docs.filter(x => x.cartella_id === c.id);
    return `<h2 class="sotto" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">${icona("cartella")} ${esc(c.nome)}
        <span class="mono piccolo" style="font-weight:400">${esc(c.percorso)}</span><span class="spazio"></span>
        <button class="btn piccolo-btn no-stampa" data-reindex="${c.id}">${icona("aggiorna")} Reindicizza tutto</button></h2>
      <div class="carta tabella-box"><table class="tabella"><thead><tr><th>Documento</th><th class="num">Pagine</th><th class="num">OCR</th><th class="num">Pezzi</th><th class="num">Tempo</th><th>Stato</th></tr></thead>
      <tbody>${d.map(x => `<tr style="cursor:pointer" data-doc="${x.id}">
        <td><b style="font-weight:600">${esc(x.nome)}</b><div class="piccolo mono">${esc(x.relpath)}</div></td>
        <td class="num">${x.pagine}</td><td class="num">${x.pagine_ocr ? `<span class="tag ocr">${x.pagine_ocr}</span>` : "—"}</td>
        <td class="num">${x.pezzi}</td><td class="num">${x.secondi != null ? secondi(x.secondi) : "—"}</td>
        <td>${x.errore ? `<span class="tag no" title="${esc(x.errore)}">errore</span>` : '<span class="tag ok">indicizzato</span>'}</td></tr>`).join("")
        || '<tr><td colspan="6" class="piccolo">Ancora vuota.</td></tr>'}</tbody></table></div>`;
  }).join("");
  box.addEventListener("click", async e => {
    const r = e.target.closest("[data-reindex]");
    if (r) { await api(`/api/cartelle/${r.dataset.reindex}/reindicizza`, { metodo: "POST" }); biglietto(`${icona("aggiorna")}<div><b>Rileggo tutta la cartella</b><div class="piccolo">Segui il Registro.</div></div>`); return; }
    const t = e.target.closest("[data-doc]");
    if (t) apriDocumento(+t.dataset.doc);
  });
}

async function apriDocumento(id) {
  const d = await api(`/api/documenti/${id}`);
  const doc = d.documento;
  const velo = document.createElement("div"); velo.className = "velo";
  const pan = document.createElement("aside"); pan.className = "cassetto-doc";
  const unita = doc.unita === "sezione" ? "Sezione" : "Pagina";
  pan.innerHTML = `<header><div style="flex:1;min-width:0"><div class="piccolo mono">${esc(doc.relpath)}</div>
      <h2 class="titolo" style="margin:4px 0 6px;font-size:24px">${esc(doc.nome)}</h2>
      <div class="piccolo">${doc.pagine} ${doc.unita === "sezione" ? "sezioni" : "pagine"} · ${d.pezzi.length} pezzi${doc.pagine_ocr ? ` · ${doc.pagine_ocr} con OCR` : ""}</div></div>
      <a class="btn piccolo-btn" href="${linkDocumento(doc.id, 1, doc.nome)}" target="_blank">${icona("doc")} Originale</a>
      <button class="btn piccolo-btn" id="re-doc">${icona("aggiorna")}</button>
      <button class="btn fantasma piccolo-btn" id="chiudi" aria-label="Chiudi">${icona("croce")}</button></header>
    <div class="corpo">
      ${doc.errore ? `<div class="nota errore" style="margin-bottom:14px">${icona("avviso")}<div>${esc(doc.errore)}</div></div>` : ""}
      ${d.pagine.map(p => `<div class="pagina-testo"><h4>${unita} ${p.numero} ${p.ocr ? '<span class="tag ocr">letta con OCR</span>' : '<span class="tag neutro">testo</span>'}</h4><pre>${esc(p.testo || "(vuota)")}</pre></div>`).join("")}
      <h2 class="sotto">I pezzi e i loro vettori</h2>
      ${d.pezzi.map((z, i) => `<div class="pezzo"><div class="piccolo mono" style="margin-bottom:6px">pezzo ${i + 1} · ${unita.toLowerCase()} ${z.pagina} · ${z.testo.length} caratteri</div>
        ${esc(z.testo.slice(0, 340))}${z.testo.length > 340 ? "…" : ""}
        <div class="numeri" style="margin-top:6px;color:var(--verderame)">${z.vettore_anteprima ? `[${z.vettore_anteprima.join(", ")}, … ${numero(z.dimensioni)} numeri]` : "vettore mancante"}</div></div>`).join("")}
    </div>`;
  document.body.append(velo, pan);
  const chiudi = () => { velo.remove(); pan.remove(); };
  velo.onclick = chiudi; $("#chiudi", pan).onclick = chiudi;
  $("#re-doc", pan).onclick = async () => { await api(`/api/documenti/${id}/reindicizza`, { metodo: "POST" }); biglietto(`${icona("aggiorna")}<div><b>Rileggo ${esc(doc.nome)}</b></div>`); chiudi(); };
  document.addEventListener("keydown", function esc_(e) { if (e.key === "Escape") { chiudi(); document.removeEventListener("keydown", esc_); } });
}

// ============ IV. Laboratorio ============
function sezLaboratorio() {
  C.innerHTML = `<section class="sezione">${testata("V · Dietro le quinte", "Laboratorio di ricerca",
    "La stessa domanda vista dalle due ricerche, poi la fusione. È quello che succede prima che il modello scriva una parola.")}
    <div class="carta" style="padding:14px;display:flex;gap:10px;margin-bottom:18px">
      <input class="campo" id="lab-q" value="${esc(A.stato?.domande_esempio?.[1] || "")}" style="font-size:16px" aria-label="Domanda">
      <button class="btn pieno" id="lab-vai">${icona("lente")} Cerca</button></div>
    <div id="lab-esito"></div></section>`;
  const vai = async () => {
    const out = $("#lab-esito");
    out.innerHTML = `<p class="piccolo">Cerco<span class="puntini"></span></p>`;
    try {
      const r = await api("/api/laboratorio/cerca", { metodo: "POST", dati: { domanda: $("#lab-q").value } });
      const li = (x, extra = "") => `<li data-p="${x.pezzo_id}"><b>${esc(nomeBreve(x.nome))} · p. ${x.pagina}</b><span class="piccolo">${extra}${esc((x.testo || "").slice(0, 120))}…</span></li>`;
      out.innerHTML = `
        <p class="piccolo" style="margin-top:0">Query per parole: <span class="mono" style="color:var(--ocra)">${esc(r.query_parole || "—")}</span> · vettore della domanda ${r.tempi.vettore_domanda_ms} ms · ricerca ${r.tempi.ricerca_ms} ms</p>
        <div class="tre-colonne">
          <div class="carta colonna" style="--c:var(--ocra)"><h3>Per parole</h3><span class="piccolo">BM25 su FTS5, con i sinonimi</span><ol>${r.parole.map(x => li(x, `punteggio ${x.punteggio.toFixed(2)} · `)).join("") || '<li class="piccolo">nessuna parola trovata</li>'}</ol></div>
          <div class="carta colonna" style="--c:var(--verderame)"><h3>Per significato</h3><span class="piccolo">vicinanza tra vettori (0–1)</span><ol>${r.significato.map(x => li(x, `${x.punteggio.toFixed(3)} · `)).join("")}</ol></div>
          <div class="carta colonna" style="--c:var(--timbro)"><h3>Fusione RRF</h3><span class="piccolo">quello che arriva al modello</span><ol>${r.fusa.map(x => li(x, `parole ${x.rango_parole ? "#" + x.rango_parole : "—"} · significato ${x.rango_significato ? "#" + x.rango_significato : "—"} · `)).join("")}</ol></div>
        </div>
        <h2 class="sotto">Il messaggio che riceve il modello</h2>
        <pre class="prompt">${esc(r.messaggi[1].content)}</pre>`;
      $$("li[data-p]", out).forEach(l => {
        l.addEventListener("mouseenter", () => $$(`li[data-p="${l.dataset.p}"]`, out).forEach(x => x.classList.add("bersaglio")));
        l.addEventListener("mouseleave", () => $$(`li.bersaglio`, out).forEach(x => x.classList.remove("bersaglio")));
      });
    } catch (e) { out.innerHTML = errore(e); }
  };
  $("#lab-vai").onclick = vai;
  $("#lab-q").addEventListener("keydown", e => e.key === "Enter" && vai());
  vai();
}

// ============ V. Banco prova ============
async function sezProva() {
  C.innerHTML = `<section class="sezione">${testata("VI · La prova finale", "Banco prova dei modelli",
    "Le tre domande sulla data-room di Crinale, una per ogni modello scelto. L'app controlla da sola risposta e citazione.")}
    <div id="prove-attese"></div>
    <div class="carta" style="padding:18px;margin:16px 0" id="scelta-prova"><p class="piccolo">Chiedo i modelli<span class="puntini"></span></p></div>
    <div id="esiti-prova"></div></section>`;
  const [stp, mod] = await Promise.all([api("/api/prova"), api("/api/modelli")]);
  $("#prove-attese").innerHTML = `<div class="passi" style="margin-top:0">${stp.prove.map((p, i) => `
    <div class="carta passo"><h3><i>${i + 1}</i> ${esc(p.domanda)}</h3><p><b>Attesa:</b> ${esc(p.attesa)}</p>
    ${p.fonte ? `<p class="mono piccolo" style="margin-top:6px">${esc(p.fonte[0])} · p. ${p.fonte[1]}</p>` : ""}</div>`).join("")}</div>`;
  const preferiti = /spark|minicpm5/i;
  const gruppi = ["ollama", "lmstudio"].map(f => ({ f, e: mod[f] }));
  const nomiF = { ollama: "Ollama", lmstudio: "LM Studio", openrouter: "OpenRouter" };
  $("#scelta-prova").innerHTML = `
    ${gruppi.map(({ f, e }) => `<label class="etichetta" style="margin-top:6px">${nomiF[f]} ${e.acceso ? "" : "· spento"}</label>
      <div class="selettore-modelli">${(e.modelli || []).map(m => `<label><input type="checkbox" data-f="${f}" value="${esc(m.id)}" ${preferiti.test(m.id) ? "checked" : ""}>
        <span class="mono">${esc(m.id)}</span></label>`).join("") || '<span class="piccolo">nessun modello</span>'}</div>`).join("")}
    ${mod.openrouter?.chiave ? `<label class="etichetta" style="margin-top:12px">OpenRouter (escono gli estratti)</label>
      <input class="campo mono" id="or-modello" placeholder="per esempio qwen/qwen3.8-27b" style="max-width:420px">` : `<p class="piccolo">OpenRouter: nessuna chiave impostata.</p>`}
    <div style="display:flex;gap:16px;align-items:center;margin-top:16px;flex-wrap:wrap">
      <button class="btn pieno" id="avvia-prova">${icona("spunta")} Avvia la prova</button>
      <select class="campo" id="prova-modo" style="width:auto"><option value="auto">Lettura automatica</option><option value="tutto">Tutto l'archivio</option><option value="ricerca">Solo la ricerca (RAG)</option></select>
      <label class="interruttore"><input type="checkbox" id="prova-ragiona"> Lascia ragionare i modelli (più lento)</label>
      <span class="piccolo" id="avanzamento"></span></div>
    <div class="barra" style="margin-top:12px"><i id="barra-prova" style="width:0"></i></div>`;
  $("#avvia-prova").onclick = async () => {
    const modelli = $$("#scelta-prova input[data-f]:checked").map(i => ({ fornitore: i.dataset.f, modello: i.value }));
    const or = $("#or-modello")?.value.trim();
    if (or) modelli.push({ fornitore: "openrouter", modello: or });
    try { await api("/api/prova", { metodo: "POST", dati: { modelli, ragionamento: $("#prova-ragiona").checked, modo: $("#prova-modo").value } }); seguiProva(); }
    catch (e) { biglietto(`${icona("avviso")}<div><b>Non parte</b><div class="piccolo">${esc(e.message)}</div></div>`, { colore: "var(--timbro)" }); }
  };
  if (stp.in_corso) seguiProva(); else disegnaEsiti(stp.risultati?.length ? stp.risultati : stp.ultima?.risultati, stp.prove, !stp.risultati?.length && stp.ultima);
}

function seguiProva() {
  clearInterval(A.timerProva);
  $("#avvia-prova").disabled = true;
  A.timerProva = setInterval(async () => {
    if (!$("#barra-prova")) return clearInterval(A.timerProva);
    const s = await api("/api/prova");
    $("#barra-prova").style.width = (s.totale ? (s.fatti / s.totale) * 100 : 0) + "%";
    $("#avanzamento").innerHTML = s.in_corso ? `${s.fatti}/${s.totale} · ${esc(s.attuale?.modello || "")} · ${esc(s.attuale?.prova || "")}<span class="puntini"></span>` : "Fatto.";
    disegnaEsiti(s.risultati, s.prove);
    if (!s.in_corso) { clearInterval(A.timerProva); $("#avvia-prova").disabled = false; }
  }, 1500);
}

function disegnaEsiti(ris, prove, salvata) {
  const out = $("#esiti-prova");
  if (!out || !ris?.length) { if (out) out.innerHTML = ""; return; }
  const chiavi = [...new Set(ris.map(r => r.fornitore + "\u0000" + r.modello))];
  const ok = ris.filter(r => r.ok).length;
  out.innerHTML = `<h2 class="sotto">Risultati ${salvata ? `<span class="piccolo" style="font-weight:400">· ultima prova salvata, ${new Date(salvata.quando * 1000).toLocaleString("it-IT")}</span>` : ""}</h2>
    <p class="piccolo">${ok} risposte giuste su ${ris.length}. Clicca un esito per leggere la risposta.</p>
    <div class="carta tabella-box"><table class="matrice-prove"><thead><tr><th>Modello</th>${prove.map((p, i) => `<th>${i + 1} · ${esc(p.id)}</th>`).join("")}<th>Totale</th></tr></thead><tbody>
    ${chiavi.map(k => {
      const [f, m] = k.split("\u0000");
      const righe = prove.map(p => ris.find(r => r.fornitore === f && r.modello === m && r.prova === p.id));
      const tot = righe.filter(r => r?.ok).length;
      const modo = righe.find(r => r?.modo)?.modo;
      return `<tr><td><div class="mono" style="font-size:12.5px">${esc(nomeModello(m))}</div><div class="piccolo">${esc({ ollama: "Ollama", lmstudio: "LM Studio", openrouter: "OpenRouter" }[f])}${modo ? ` · ${modo === "tutto" ? "tutto l'archivio" : "ricerca"}` : ""}</div></td>
        ${righe.map(r => !r ? `<td class="piccolo">in attesa</td>` : `<td><button class="esito" data-r="${ris.indexOf(r)}">
          <span class="voto ${r.ok ? "si" : "no"}">${icona(r.ok ? "spunta" : "croce")} ${r.ok ? "GIUSTA" : r.errore ? "ERRORE" : "SBAGLIATA"}</span>
          <span class="piccolo">risposta ${r.contenuto ? "✓" : "✗"} · citazione ${r.citazione ? "✓" : "✗"} · ${secondi(r.secondi)}</span></button></td>`).join("")}
        <td><b class="titolo" style="font-size:20px">${tot}/${prove.length}</b></td></tr>`;
    }).join("")}</tbody></table></div><div id="dettaglio-esito"></div>`;
  $$(".esito", out).forEach(b => b.onclick = () => {
    const r = ris[+b.dataset.r];
    $("#dettaglio-esito").innerHTML = `<div class="carta" style="padding:18px;margin-top:14px">
      <div class="piccolo mono">${esc(r.modello)} · ${esc(r.prova)}</div><h3 class="titolo" style="margin:6px 0">${esc(r.domanda)}</h3>
      ${r.errore ? errore(r.errore) : `<div style="white-space:pre-wrap;font-size:15px;line-height:1.6">${esc(r.risposta || "(vuota)")}</div>`}
      <p class="piccolo">Fonti citate: ${(r.fonti || []).map(f => `${esc(f.nome)} p. ${f.pagina}`).join(" · ") || "nessuna"} · attesa: ${esc(r.attesa)}</p></div>`;
  });
}

// ============ VI. MCP ============
async function sezMcp() {
  C.innerHTML = `<section class="sezione">${testata("VII · Server MCP", "Collegare Archivio agli altri programmi",
    "Lo stesso stile del server MCP di Crinale: tu colleghi entrambi a Unsloth Studio (o a qualunque client MCP) e il modello usa documenti e dati insieme.")}
    <div class="nota" style="margin-bottom:18px">${icona("spina")}<div><b>In Unsloth Studio:</b> Add custom MCP → incolla l'URL → autenticazione nessuna.
      Per i documenti: <span class="mono">http://127.0.0.1:4100/mcp/documenti</span>. Per i numeri di Crinale: <span class="mono">http://127.0.0.1:5400/mcp</span>.</div></div>
    <div class="griglia" id="mcp-elenco"><p class="piccolo">Busso ai server<span class="puntini"></span></p></div>
    <h2 class="sotto">Prova uno strumento</h2>
    <div class="carta" style="padding:18px">
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
        <div><label class="etichetta">Strumento</label><select class="campo" id="mcp-str" style="width:auto">
          <option>descrivi_archivio</option><option>cerca_nei_documenti</option><option>leggi_pagina</option></select></div>
        <div style="flex:1;min-width:220px" id="mcp-arg"></div>
        <button class="btn pieno" id="mcp-vai">Chiama</button></div>
      <pre class="prompt" id="mcp-out" style="margin-top:14px">Il risultato arriva qui, esattamente come lo vede Unsloth.</pre></div>
    <h2 class="sotto">Server MCP esterni</h2>
    <div class="carta" style="padding:18px"><p class="piccolo" style="margin-top:0">Altri server da tenere d'occhio. Solo indirizzi locali.</p>
      <div style="display:grid;grid-template-columns:1fr 1.4fr 2fr auto;gap:8px">
        <input class="campo" id="est-nome" placeholder="Nome"><input class="campo mono" id="est-url" placeholder="http://127.0.0.1:5400/mcp">
        <input class="campo" id="est-desc" placeholder="A cosa serve"><button class="btn" id="est-agg">${icona("piu")} Aggiungi</button></div></div>
  </section>`;
  const argomenti = () => {
    const s = $("#mcp-str").value;
    $("#mcp-arg").innerHTML = s === "cerca_nei_documenti"
      ? `<label class="etichetta">domanda</label><input class="campo" id="a1" value="${esc(A.stato?.domande_esempio?.[0] || "")}">`
      : s === "leggi_pagina" ? `<div style="display:flex;gap:8px"><div style="flex:1"><label class="etichetta">documento</label><input class="campo" id="a1" value="13_Rinnovo_Nordwand_2024.pdf"></div>
          <div style="width:90px"><label class="etichetta">pagina</label><input class="campo" id="a2" type="number" value="2"></div></div>` : "";
  };
  $("#mcp-str").onchange = argomenti; argomenti();
  $("#mcp-vai").onclick = async () => {
    const s = $("#mcp-str").value;
    const arg = s === "cerca_nei_documenti" ? { domanda: $("#a1").value } : s === "leggi_pagina" ? { documento: $("#a1").value, pagina: +$("#a2").value } : {};
    $("#mcp-out").textContent = "…";
    try { $("#mcp-out").textContent = (await api("/api/mcp/prova", { metodo: "POST", dati: { strumento: s, argomenti: arg } })).testo; }
    catch (e) { $("#mcp-out").textContent = "ERRORE: " + e.message; }
  };
  $("#est-agg").onclick = async () => {
    const imp = await api("/api/impostazioni");
    const nuovo = { nome: $("#est-nome").value, url: $("#est-url").value, descrizione: $("#est-desc").value };
    if (!/^http:\/\/(127\.0\.0\.1|localhost)/.test(nuovo.url)) return biglietto(`${icona("avviso")}<div><b>Solo indirizzi locali</b><div class="piccolo">http://127.0.0.1:…</div></div>`, { colore: "var(--timbro)" });
    await api("/api/impostazioni", { metodo: "POST", dati: { mcp_esterni: [...imp.mcp_esterni, nuovo] } });
    disegnaMcp();
  };
  disegnaMcp();
}
async function disegnaMcp() {
  const elenco = await api("/api/mcp");
  $("#mcp-elenco").innerHTML = elenco.map(m => `<div class="carta mcp">
    <div style="display:flex;gap:10px;align-items:center"><span class="pallino ${m.acceso ? "acceso" : "spento"}"></span>
      <h3 class="titolo" style="margin:0;font-size:18px;flex:1">${esc(m.nome)}</h3>${m.proprio ? '<span class="tag neutro">archivio</span>' : '<span class="tag neutro">esterno</span>'}</div>
    <p class="piccolo" style="margin:0">${esc(m.descrizione || "")}</p>
    <div class="url"><code>${esc(m.url)}</code><button class="btn fantasma piccolo-btn" data-copia="${esc(m.url)}">${icona("copia")}</button></div>
    ${m.acceso ? `<div class="strumenti">${(m.strumenti || []).map(t => `<span>${esc(t)}</span>`).join("")}</div>`
      : `<p class="piccolo" style="margin:0">${m.modulo ? "Spento: accendi il modulo." : `Spento. Avvio: <span class="mono">${esc(m.avvio || "")}</span>`}</p>`}
    ${!m.proprio ? `<button class="btn fantasma piccolo-btn" data-togli="${esc(m.id)}" style="justify-self:start">${icona("cestino")} Togli</button>` : ""}
  </div>`).join("");
  $$("[data-copia]").forEach(b => b.onclick = () => copia(b.dataset.copia, b));
  $$("[data-togli]").forEach(b => b.onclick = async () => {
    const imp = await api("/api/impostazioni");
    await api("/api/impostazioni", { metodo: "POST", dati: { mcp_esterni: imp.mcp_esterni.filter(x => x.id !== b.dataset.togli) } });
    disegnaMcp();
  });
}

// ============ VII. Moduli ============
async function sezModuli() {
  const st = await api("/api/stato");
  C.innerHTML = `<section class="sezione">${testata("VIII · Moduli", "Pezzi da accendere e spegnere",
    "Un modulo aggiunge una scheda alla vista del cliente e, se serve, un proprio server MCP. Si accende qui, senza riavviare.")}
    ${st.moduli.map(m => `<div class="carta modulo">
      <div><div style="display:flex;gap:10px;align-items:center;margin-bottom:8px"><span class="tag ocr">${esc(m.stato)}</span>${m.acceso ? '<span class="tag ok">acceso</span>' : '<span class="tag neutro">spento</span>'}</div>
        <h2 class="titolo" style="margin:0 0 6px;font-size:26px">${esc(m.nome)}</h2>
        <p style="margin:0 0 12px;max-width:62ch">${esc(m.descrizione)}</p>
        <div class="dett piccolo" style="display:grid;gap:4px">
          <div>Scheda nel cliente: <span class="mono">http://127.0.0.1:4100/#bi</span></div>
          <div>Server MCP del modulo: <span class="mono">http://127.0.0.1:4100${esc(m.mcp)}</span></div>
          <div>Fonte dati: <span class="mono">${esc(m.fonte)}</span> (Crinale MCP)</div></div></div>
      <label class="interruttore" style="font-size:15px"><input type="checkbox" data-mod="${m.id}" ${m.acceso ? "checked" : ""}> ${m.acceso ? "Acceso" : "Spento"}</label>
    </div>`).join("")}</section>`;
  $$("[data-mod]").forEach(i => i.onchange = async () => {
    await api(`/api/moduli/${i.dataset.mod}`, { metodo: "POST", dati: { acceso: i.checked } });
    biglietto(`${icona("grafico")}<div><b>Modulo ${i.checked ? "acceso" : "spento"}</b><div class="piccolo">${i.checked ? "Nella vista cliente compare la scheda BI." : "La scheda BI sparisce dal cliente."}</div></div>`);
    sezModuli();
  });
}

// ============ VIII. Impostazioni ============
async function sezImpostazioni() {
  const [imp, mod] = await Promise.all([api("/api/impostazioni"), api("/api/modelli")]);
  const visione = [...(mod.lmstudio.modelli || []).map(m => ({ f: "lmstudio", id: m.id, v: m.tipo === "vlm" })), ...(mod.ollama.modelli || []).map(m => ({ f: "ollama", id: m.id, v: true }))];
  C.innerHTML = `<section class="sezione">${testata("IX · Impostazioni", "Come lavora l'app",
    "Salvate in indice/impostazioni.json, accanto all'indice. Mai nel codice.")}
    <div class="griglia" style="grid-template-columns:repeat(auto-fill,minmax(340px,1fr))">
      <div class="carta comp"><div class="testa"><h3>OCR</h3></div>
        <p class="serve">Per le pagine scansionate. Tesseract è veloce; un modello di visione (per esempio Unlimited OCR di Baidu, o qwen3.6 in LM Studio) è più preciso ma più lento.</p>
        <label class="interruttore"><input type="radio" name="ocr" value="tesseract" ${imp.ocr.motore !== "visione" ? "checked" : ""} style="appearance:auto;width:auto;height:auto;background:none"> Tesseract (italiano)</label>
        <label class="interruttore"><input type="radio" name="ocr" value="visione" ${imp.ocr.motore === "visione" ? "checked" : ""} style="appearance:auto;width:auto;height:auto;background:none"> Modello di visione in locale</label>
        <select class="campo" id="ocr-modello"><option value="">— scegli il modello —</option>
          ${visione.map(m => `<option value="${m.f}|${esc(m.id)}" ${imp.ocr.modello === m.id && imp.ocr.fornitore === m.f ? "selected" : ""}>${m.f === "lmstudio" ? "LM Studio" : "Ollama"} · ${esc(m.id)}${m.v && m.f === "lmstudio" ? " (vede immagini)" : ""}</option>`).join("")}</select>
        <p class="piccolo">Vale per i prossimi documenti. Per rifare l'OCR: Indice → Reindicizza tutto.</p></div>
      <div class="carta comp"><div class="testa"><h3>Ricerca e pezzi</h3></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div><label class="etichetta">Estratti al modello</label><input class="campo" id="k" type="number" min="1" max="20" value="${imp.ricerca.estratti}"></div>
          <div><label class="etichetta">Candidati per ricerca</label><input class="campo" id="cand" type="number" min="10" max="200" value="${imp.ricerca.candidati}"></div>
          <div><label class="etichetta">Pezzo (caratteri)</label><input class="campo" id="dim" type="number" value="${imp.pezzi.dimensione}"></div>
          <div><label class="etichetta">Sovrapposizione</label><input class="campo" id="sov" type="number" value="${imp.pezzi.sovrapposizione}"></div></div>
        <p class="piccolo">I pezzi nuovi valgono dalla prossima indicizzazione.</p></div>
    </div>
    <h2 class="sotto">Vocabolario dei sinonimi</h2>
    <p class="piccolo" style="margin-top:-4px">Una riga, un gruppo di parole equivalenti. Se la domanda contiene una parola del gruppo, la ricerca per parole cerca anche le altre.</p>
    <textarea class="campo mono" id="sin" rows="10">${esc(imp.sinonimi.join("\n"))}</textarea>
    <h2 class="sotto">Domande di esempio</h2>
    <textarea class="campo" id="esempi" rows="4">${esc(imp.domande_esempio.join("\n"))}</textarea>
    <div style="margin-top:18px"><button class="btn pieno" id="salva">${icona("spunta")} Salva</button></div></section>`;
  $("#salva").onclick = async () => {
    const [f, ...m] = ($("#ocr-modello").value || "|").split("|");
    try {
      await api("/api/impostazioni", { metodo: "POST", dati: {
        ocr: { motore: $('input[name="ocr"]:checked').value, fornitore: f || "lmstudio", modello: m.join("|"), lingua: "ita" },
        ricerca: { estratti: +$("#k").value, candidati: +$("#cand").value },
        pezzi: { dimensione: +$("#dim").value, sovrapposizione: +$("#sov").value },
        sinonimi: $("#sin").value.split("\n"), domande_esempio: $("#esempi").value.split("\n"),
      } });
      biglietto(`${icona("spunta")}<div><b>Impostazioni salvate</b></div>`);
    } catch (e) { biglietto(`${icona("avviso")}<div><b>Non salvate</b><div class="piccolo">${esc(e.message)}</div></div>`, { colore: "var(--timbro)" }); }
  };
}

// ============ IX. Registro ============
function sezRegistro() {
  C.innerHTML = `<section class="sezione">${testata("X · Registro", "Quello che fa l'app, in diretta",
    "Indicizzazioni, OCR, file aggiunti o tolti dalle cartelle. Prova: copia un PDF nella cartella e guardalo comparire qui.")}
    <div class="carta registro" id="reg"></div></section>`;
  disegnaRegistro();
}
function disegnaRegistro() {
  const r = $("#reg");
  if (!r) return;
  const giu = r.scrollHeight - r.scrollTop - r.clientHeight < 40;
  r.innerHTML = A.registro.map(x => `<div><span class="t">${ora(x.t)}</span><span class="${x.livello}">${esc(x.testo)}</span></div>`).join("") || '<span class="piccolo">Ancora niente.</span>';
  if (giu) r.scrollTop = r.scrollHeight;
}

// ============ instradamento e stato ============
const SEZIONI = { sistema: sezSistema, come: sezCome, indice: sezIndice, laboratorio: sezLaboratorio, prova: sezProva, mcp: sezMcp, moduli: sezModuli, impostazioni: sezImpostazioni, registro: sezRegistro };
function instrada() {
  const id = (location.hash.slice(1) || "sistema");
  $$("#nav a").forEach(a => a.toggleAttribute("aria-current", a.getAttribute("href") === "#" + id));
  clearInterval(A.timerProva);
  (SEZIONI[id] || sezSistema)();
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", instrada);

async function aggiornaStato() {
  try {
    const st = await api(`/api/stato?dopo=${A.dopo}`);
    A.stato = st;
    if (st.registro.length) { A.registro.push(...st.registro); A.registro = A.registro.slice(-400); A.dopo = st.registro.at(-1).t; disegnaRegistro(); }
    const i = st.indicizzazione;
    $("#stato-indice").innerHTML = i.attivo ? `<span class="pallino lavora"></span> indicizzo ${esc(i.file || "")}<span class="puntini"></span>`
      : `${numero(st.totale.documenti)} documenti · ${numero(st.totale.pezzi)} pezzi`;
  } catch { $("#stato-indice").innerHTML = `<span class="pallino spento"></span> app non raggiungibile`; }
}

(async () => {
  await aggiornaStato();
  instrada();
  setInterval(aggiornaStato, 2000);
})();
