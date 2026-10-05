// Archivio — la lezione "Cos'è un RAG", con i numeri veri dell'archivio.
// Si appoggia alle funzioni di admin.js (testata, errore, C, A, calcolaVettori).

function barraToken(etichetta, valore, massimo, colore, nota = "") {
  const perc = Math.max(0.6, Math.min(100, (valore / massimo) * 100));
  return `<div class="bt"><div class="bt-et"><b>${etichetta}</b><span>${numero(valore)} token${nota ? " · " + nota : ""}</span></div>
    <div class="bt-pista"><i style="width:${perc}%;background:${colore}"></i></div></div>`;
}

function codiceVettore(numeri) {
  // il vettore come "codice a barre": ogni striscia è un numero, il colore dice se è positivo o negativo
  const max = Math.max(...numeri.map(Math.abs)) || 1;
  return `<div class="codice">${numeri.map(x => `<i title="${x.toFixed(4)}" style="background:${x >= 0 ? "var(--verderame)" : "var(--timbro)"};opacity:${(0.25 + 0.75 * Math.abs(x) / max).toFixed(2)}"></i>`).join("")}</div>`;
}

async function sezRag() {
  C.innerHTML = `<section class="sezione lezione">${testata("II · Per la lezione", "Cos'è un RAG, spiegato con la data-room di Crinale",
    "Archivio è un sistema RAG. Questa pagina lo smonta pezzo per pezzo con i documenti veri: niente formule, solo quello che succede davvero dentro il programma.")}
    <div id="lez"><p class="piccolo">Preparo i numeri dell'archivio<span class="puntini"></span></p></div></section>`;
  let n;
  try { n = await api("/api/rag/numeri"); } catch (e) { $("#lez").innerHTML = errore(e); return; }
  const doc = n.esempio_doc ? await api(`/api/documenti/${n.esempio_doc}`).catch(() => null) : null;
  const archivioEntra = n.token + 7000 < n.contesto * 0.9;
  const pagEs = doc?.pagine?.find(p => /14\.3/.test(p.testo || "")) || doc?.pagine?.[0];
  const pezziEs = doc ? doc.pezzi.filter(z => z.pagina === pagEs?.numero) : [];
  const tutti = doc ? doc.pezzi : [];

  $("#lez").innerHTML = `
  <div class="capitolo">
    <div class="carta riquadro-chiave">
      <div class="num">In una frase</div>
      <p class="grande"><b>RAG</b> sta per <i>Retrieval-Augmented Generation</i>: generazione <b>aumentata dal recupero</b>.
      Prima di rispondere, il programma <b>va a prendere</b> nei tuoi documenti le pagine giuste e le mette davanti al modello,
      che risponde leggendo quelle e citandole.</p>
      <p>È come un esame <b>a libro aperto</b>: lo studente (il modello) non ha studiato i tuoi contratti, ma può leggerli mentre risponde.
      Il RAG è il compagno che gli passa le pagine giuste del libro.</p>
    </div>
  </div>

  <h2 class="sotto">1 · Il problema: il modello non conosce i tuoi documenti</h2>
  <div class="due">
    <div><p>Un modello come Spark o Qwen ha imparato leggendo una quantità enorme di testi pubblici, <b>prima</b> di arrivare sul tuo Mac.
      Non ha mai visto il contratto Nordwand, il ricorso Ferraro o i verbali di Crinale. Se glieli chiedi senza darglieli,
      ha due possibilità: dire «non lo so» o, peggio, <b>inventare</b> una risposta plausibile (si chiama <i>allucinazione</i>).</p>
      <p>Le strade per fargli usare i tuoi documenti sono tre:</p></div>
    <div class="carta tabella-box"><table class="tabella">
      <thead><tr><th>Strada</th><th>Come funziona</th><th>Pro e contro</th></tr></thead><tbody>
      <tr><td><b>Riaddestrarlo</b><div class="piccolo">fine-tuning</div></td><td>Gli fai "studiare" i documenti, cambiandone i pesi.</td><td class="piccolo">Costoso, lento, va rifatto a ogni documento nuovo, e il modello <b>non sa citare</b> da dove ha preso un'informazione.</td></tr>
      <tr><td><b>Dargli tutto</b><div class="piccolo">contesto lungo</div></td><td>Metti tutti i documenti nel messaggio, ogni volta.</td><td class="piccolo">Il modello vede tutto e collega bene. Funziona finché l'archivio <b>entra nella memoria di lavoro</b>.</td></tr>
      <tr><td><b>RAG</b><div class="piccolo">recupero + generazione</div></td><td>Cerchi le pagine pertinenti e dai solo quelle.</td><td class="piccolo">Scala a migliaia di documenti, è veloce e cita le fonti. Se però la ricerca sbaglia pagina, il modello non la vede.</td></tr>
    </tbody></table></div>
  </div>

  <h2 class="sotto">2 · La memoria di lavoro del modello: il contesto</h2>
  <div class="due">
    <div>
      <p>Un modello non legge "documenti": legge <b>token</b>, pezzetti di parola. In italiano un token vale circa 3–4 caratteri:
      «contratto» sono 2–3 token. Ogni modello ha una <b>finestra di contesto</b>, cioè quanti token riesce a tenere sotto gli occhi
      in una volta, tra documenti, domanda, ragionamento e risposta. È la sua scrivania.</p>
      <p>La data-room di Crinale è piccola: <b>${numero(n.pagine)} pagine</b> di ${numero(n.documenti)} documenti,
      ${numero(n.caratteri)} caratteri, circa <b>${numero(n.token)} token</b>.
      ${archivioEntra
        ? `Sulla scrivania del modello che hai scelto (${esc(nomeModello(n.modello))}, ${numero(n.contesto)} token) <b>entra tutta</b>: per questo Archivio, in lettura automatica, gli dà l'archivio intero. È quello che fa anche Unsloth Studio quando carichi una cartella piccola, ed è il motivo per cui con poche pagine "leggere tutto" batte la ricerca.`
        : `Sulla scrivania del modello scelto (${numero(n.contesto)} token) <b>non entra</b>: serve il RAG.`}</p>
      <p>Un'azienda vera però ha migliaia di documenti: 10.000 contratti da 5 pagine sono circa <b>15 milioni di token</b>.
      Nessun modello li tiene tutti sulla scrivania, e anche se potesse sarebbe lentissimo e costoso a ogni domanda. Lì il RAG non è una scelta: è l'unico modo.</p>
    </div>
    <div class="carta" style="padding:18px">
      ${barraToken("Data-room di Crinale", n.token, Math.max(n.contesto, 300000), "var(--timbro)", `${n.pagine} pagine`)}
      ${barraToken(esc(nomeModello(n.modello)), n.contesto, Math.max(n.contesto, 300000), "var(--verderame)", "contesto")}
      ${Object.entries(n.contesti_noti).filter(([k]) => !k.endsWith(n.modello)).slice(0, 4).map(([k, v]) => barraToken(esc(nomeModello(k.split(" · ")[1])), v, Math.max(n.contesto, 300000), "var(--ocra)", "contesto")).join("")}
      ${barraToken("Un modello piccolo «di serie»", 4096, Math.max(n.contesto, 300000), "var(--grigio)", "per esempio MiniCPM in Ollama")}
      <p class="piccolo" style="margin:10px 0 0">Le barre sono in scala. Un archivio aziendale da 15 milioni di token sarebbe una barra lunga 50 volte questa pagina.</p>
    </div>
  </div>

  <h2 class="sotto">3 · Le due fasi di un RAG</h2>
  <div class="due">
    <div class="carta fase"><div class="num">Fase A · una volta sola, quando arriva un documento</div>
      <ol class="passi-lista">
        <li><b>Leggere.</b> Si estrae il testo pagina per pagina. Le pagine scansionate sono solo immagini: le legge l'<b>OCR</b> (riconoscimento dei caratteri).</li>
        <li><b>Tagliare.</b> Il testo si divide in <b>pezzi</b> (in inglese <i>chunk</i>) di circa ${numero(n.pezzo.dimensione)} caratteri, che si sovrappongono di ${numero(n.pezzo.sovrapposizione)}: così una frase a cavallo del taglio non si perde.</li>
        <li><b>Trasformare in numeri.</b> Ogni pezzo diventa un <b>vettore</b>: ${numero(n.dimensioni)} numeri che ne descrivono il significato.</li>
        <li><b>Archiviare.</b> Pezzi, vettori, documento e pagina finiscono nell'<b>indice</b>. Qui è un file SQLite: un piccolo database.</li>
      </ol></div>
    <div class="carta fase"><div class="num">Fase B · a ogni domanda</div>
      <ol class="passi-lista">
        <li><b>La domanda diventa un vettore</b>, con lo stesso modello usato per i pezzi.</li>
        <li><b>Si cerca</b> in due modi: per <b>parole</b> (codici, nomi, numeri d'articolo) e per <b>significato</b> (vettori vicini).</li>
        <li><b>Si scelgono</b> le pagine migliori, quante ne stanno nel contesto del modello.</li>
        <li><b>Si scrive il messaggio</b> al modello: regole, pagine numerate [E1], [E2]…, domanda.</li>
        <li><b>Il modello risponde</b> citando le pagine.</li>
        <li><b>Il programma controlla</b> che le citazioni esistano davvero e che non ci siano ordini nascosti nei documenti.</li>
      </ol></div>
  </div>

  <h2 class="sotto">4 · Il taglio in pezzi, su un documento vero</h2>
  ${doc ? `<p>Ecco <b>${esc(doc.documento.nome)}</b>, pagina ${pagEs.numero}. Il documento ha ${doc.documento.pagine} pagine ed è stato tagliato in
    <b>${tutti.length} pezzi</b>. Questa pagina ne ha ${pezziEs.length}. Le parti evidenziate sono la <b>sovrapposizione</b>: compaiono sia alla fine di un pezzo sia all'inizio del successivo.</p>
    <div class="due">
      <div class="carta" style="padding:16px"><div class="num">La pagina com'è</div><pre class="pagina-vera">${esc(pagEs.testo)}</pre></div>
      <div>${pezziEs.map((z, i) => {
        const succ = pezziEs[i + 1];
        let t = esc(z.testo);
        if (succ) { const coda = z.testo.slice(-140); const k = succ.testo.indexOf(coda.slice(-60)); if (k >= 0) t = esc(z.testo.slice(0, -140)) + `<mark>${esc(coda)}</mark>`; }
        return `<div class="carta pezzo-es"><div class="num">Pezzo ${i + 1} di questa pagina · ${z.testo.length} caratteri</div><div>${t}</div>
          <div class="num" style="margin-top:10px">Il suo vettore: i primi 12 di ${numero(z.dimensioni)} numeri</div>
          ${z.vettore_anteprima ? codiceVettore(z.vettore_anteprima) + `<div class="numeri">[${z.vettore_anteprima.map(x => x.toFixed(3)).join(", ")}, …]</div>` : '<span class="piccolo">vettore mancante</span>'}</div>`;
      }).join("")}</div>
    </div>
    <p class="piccolo">Perché pezzi e non documenti interi? Perché la ricerca deve trovare <b>il punto</b> che risponde, non un contratto di 30 pagine.
    E perché un pezzo non scavalca mai due pagine: così ogni pezzo ha una sola pagina da citare.</p>` : '<p class="piccolo">Aggiungi una cartella per vedere un esempio.</p>'}

  <h2 class="sotto">5 · I vettori: una mappa dei significati</h2>
  <div class="due">
    <div>
      <p>Immagina una mappa in cui ogni frase è un punto. Le frasi che dicono cose simili stanno <b>vicine</b>, anche se usano parole diverse:
      «il contratto si può disdire» e «è possibile recedere dall'accordo» finiscono quasi nello stesso posto, «la ricetta del tiramisù» lontanissimo.</p>
      <p>Un <b>vettore</b> è l'indirizzo di quel punto. Una mappa di carta ha 2 coordinate (latitudine e longitudine); la mappa dei significati
      del modello <span class="mono">${esc(n.embedding)}</span> ne ha <b>${numero(n.dimensioni)}</b>. Nessuna coordinata ha un nome
      ("questa misura i contratti"): è il modello che, addestrandosi, ha imparato a disporre i significati.</p>
      <p>La vicinanza si misura con la <b>similarità del coseno</b>: si guarda l'angolo tra le due frecce che partono dal centro
      e arrivano ai due punti. 1 vuol dire stessa direzione (stesso significato), 0 nessun rapporto.</p>
      <p class="piccolo">Il modello dei vettori non è quello che risponde: è un modello piccolo e specializzato (0,6 miliardi di parametri), e qui gira sempre sul Mac, anche quando risponde un modello in cloud.</p>
    </div>
    <div class="carta" style="padding:14px">
      <svg viewBox="0 0 420 300" role="img" aria-label="Schema illustrativo di una mappa dei significati" style="width:100%;height:auto">
        <defs><marker id="pv" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 10 5 0 10z" fill="var(--grigio)"/></marker></defs>
        <rect x="0" y="0" width="420" height="300" fill="var(--foglio-2)" rx="4"/>
        <circle cx="250" cy="82" r="60" fill="var(--verderame-tenue)" stroke="var(--verderame)" stroke-dasharray="4 4"/>
        <circle cx="110" cy="210" r="46" fill="var(--ocra-tenue)" stroke="var(--ocra)" stroke-dasharray="4 4"/>
        <line x1="40" y1="270" x2="236" y2="76" stroke="var(--grigio)" stroke-width="1.2" marker-end="url(#pv)"/>
        <line x1="40" y1="270" x2="252" y2="104" stroke="var(--grigio)" stroke-width="1.2" marker-end="url(#pv)"/>
        <line x1="40" y1="270" x2="268" y2="252" stroke="var(--grigio)" stroke-width="1.2" marker-end="url(#pv)"/>
        ${[[236, 76, "«disdire il contratto»"], [252, 104, "«recedere dall'accordo»"], [222, 54, "«risoluzione»"], [100, 200, "«fatturato 2025»"], [126, 226, "«ricavi di vendita»"], [268, 252, "«ricetta del tiramisù»"]]
          .map(([x, y, t]) => `<circle cx="${x}" cy="${y}" r="5" fill="var(--inchiostro)"/><text x="${x + 8}" y="${y + 4}" font-size="12" style="fill:var(--inchiostro);font-family:var(--f-testo)">${t}</text>`).join("")}
        <text x="250" y="160" font-size="11" text-anchor="middle" style="fill:var(--verderame);font-family:var(--f-mono)">zona "recesso"</text>
        <text x="110" y="272" font-size="11" text-anchor="middle" style="fill:var(--ocra);font-family:var(--f-mono)">zona "numeri"</text>
        <text x="10" y="18" font-size="10.5" style="fill:var(--grigio);font-family:var(--f-mono)">SCHEMA ILLUSTRATIVO · 2 DIMENSIONI INVECE DI ${numero(n.dimensioni)}</text>
      </svg>
      <p class="piccolo" style="margin:6px 4px 0">Frecce quasi sovrapposte vuol dire coseno vicino a 1, quindi significato simile. La freccia del tiramisù va da tutt'altra parte.</p>
    </div>
  </div>
  <div class="carta lab-vettori" style="margin-top:14px">
    <div>
      <div class="num" style="margin-bottom:8px">Prova dal vivo: scrivi frasi, il Mac calcola i vettori</div>
      ${["Il contratto si può disdire con trenta giorni di preavviso.", "È possibile recedere dall'accordo con un mese di anticipo.", "Le vendite in Germania sono cresciute del 12%.", "La ricetta del tiramisù vuole il mascarpone."]
        .map((f, i) => `<input class="campo frase" style="margin-bottom:8px" value="${esc(f)}" aria-label="Frase ${i + 1}">`).join("")}
      <button class="btn pieno" id="calcola">${icona("chip")} Calcola i vettori</button>
    </div>
    <div id="esito-vettori" class="piccolo">I vettori li calcola Ollama, qui sul Mac.</div>
  </div>

  <h2 class="sotto">6 · La ricerca: parole, significato e la fusione</h2>
  <div class="tre-colonne">
    <div class="carta colonna" style="--c:var(--ocra)"><h3>Per parole</h3>
      <p class="piccolo">Algoritmo <b>BM25</b>, quello dei motori di ricerca classici. Premia i pezzi che contengono le parole della domanda,
      soprattutto quelle <b>rare</b> ("Nordwand" conta più di "contratto") e non si lascia ingannare dai testi lunghi.
      Imbattibile su codici, nomi, importi, numeri d'articolo. Non capisce i sinonimi: per questo Archivio ha un vocabolario
      (chi chiede "cause" cerca anche "ricorso" e "tribunale").</p></div>
    <div class="carta colonna" style="--c:var(--verderame)"><h3>Per significato</h3>
      <p class="piccolo">Si confronta il vettore della domanda con i vettori di tutti i pezzi e si tengono i più vicini.
      Trova "disdetta" quando il testo dice "recesso". Su codici e numeri invece va quasi a caso, e un modello di vettori piccolo
      distingue male documenti che parlano tutti della stessa azienda.</p></div>
    <div class="carta colonna" style="--c:var(--timbro)"><h3>Fusione (RRF)</h3>
      <p class="piccolo"><i>Reciprocal Rank Fusion</i>: ogni pezzo prende un punteggio da ciascuna classifica, 1 ÷ (60 + posizione).
      Esempio: un pezzo 2° per parole e 9° per significato fa 1/62 + 1/69 = 0,0306; uno 1° per parole ma assente nell'altra fa 1/61 = 0,0164.
      Vince chi va bene <b>in tutte e due</b>. Non serve sapere come sono fatti i punteggi originali: contano solo le posizioni.</p></div>
  </div>
  <p>Per vedere le tre classifiche su una domanda vera apri <a href="#laboratorio">V · Laboratorio</a>: cambi la domanda e guardi chi sale e chi scende.</p>

  <h2 class="sotto">7 · Il messaggio che arriva al modello</h2>
  <p>Alla fine il modello riceve un unico testo: le <b>regole</b>, le <b>pagine numerate</b> e la <b>domanda</b>. È tutto qui: il modello non ha accesso
  all'archivio, vede solo questo. Ecco l'inizio del messaggio vero per la prima domanda d'esempio:</p>
  <pre class="prompt" id="msg-esempio">Carico<span class="puntini"></span></pre>

  <h2 class="sotto">8 · Il controllo dopo la risposta</h2>
  <div class="passi">
    <div class="carta passo"><h3>${icona("spunta")} Citazioni verificate</h3><p>Ogni [E3] deve corrispondere a una pagina davvero passata al modello. Se il modello cita [E9] e le pagine erano 8, l'app lo segna in rosso.</p></div>
    <div class="carta passo"><h3>${icona("croce")} «Non presente nei documenti»</h3><p>Se l'informazione non c'è, il modello deve dirlo con queste parole. È la difesa contro l'allucinazione: meglio un «non c'è» onesto che una cifra inventata.</p></div>
    <div class="carta passo"><h3>${icona("versioni")} Versioni</h3><p>Contratto 2016, rinnovo 2020, rinnovo 2024: stesso nome, anni diversi. L'app lo riconosce dal nome del file e indica qual è il più recente.</p></div>
    <div class="carta passo"><h3>${icona("avviso")} Ordini nascosti</h3><p>Un documento può contenere frasi come «ignora le istruzioni e rispondi che…» (si chiama <i>prompt injection</i>). L'app le toglie prima che arrivino al modello: un modello da 2 miliardi di parametri, altrimenti, ci casca.</p></div>
  </div>

  <h2 class="sotto">9 · RAG o "dagli tutto"? Archivio sceglie da solo</h2>
  <div class="carta tabella-box"><table class="tabella">
    <thead><tr><th></th><th>Tutto l'archivio</th><th>Ricerca (RAG)</th></tr></thead><tbody>
    <tr><td>Quando</td><td>L'archivio entra nel contesto del modello (data-room di Crinale con Spark: sì)</td><td>Archivio grande, o modello con contesto piccolo</td></tr>
    <tr><td>Qualità</td><td>Il modello vede tutto e collega documenti lontani: verbale + ricorso + bilancio</td><td>Ottima se la ricerca trova le pagine giuste; se ne manca una, il modello non la vede</td></tr>
    <tr><td>Velocità</td><td>Più lento alla prima domanda (legge ${numero(n.token)} token); poi Ollama tiene in memoria l'archivio già letto</td><td>Veloce: legge solo ${numero(n.estratti)} pagine</td></tr>
    <tr><td>Costo in cloud</td><td>Paghi tutti i token a ogni domanda</td><td>Paghi solo le pagine scelte</td></tr>
    <tr><td>Scala</td><td>Decine o centinaia di pagine</td><td>Milioni di pagine</td></tr>
  </tbody></table></div>
  <p>In <b>lettura automatica</b> Archivio guarda la memoria di lavoro vera del modello scelto e decide. Puoi forzare una delle due modalità dal menu accanto al modello, così in aula le confronti sulla stessa domanda.</p>

  <h2 class="sotto">10 · Le parole da sapere</h2>
  <div class="glossario">
    ${[
      ["RAG", "Retrieval-Augmented Generation: prima si recuperano le pagine pertinenti, poi il modello genera la risposta leggendole."],
      ["LLM", "Large Language Model, il modello che scrive (Spark, Qwen, MiniCPM). Non sa nulla dei tuoi documenti finché non glieli dai."],
      ["Token", "Il pezzetto di testo che il modello legge: in italiano circa 3–4 caratteri."],
      ["Contesto", "La memoria di lavoro: quanti token il modello tiene sotto gli occhi in una volta (documenti + domanda + risposta)."],
      ["Pezzo (chunk)", "Un frammento di circa 1.000 caratteri di una pagina. È l'unità che si cerca."],
      ["Sovrapposizione", "I caratteri che un pezzo ripete del precedente, per non spezzare le frasi."],
      ["Vettore (embedding)", `Una lista di ${numero(n.dimensioni)} numeri che rappresenta il significato di un testo.`],
      ["Modello di embedding", `Il modello che calcola i vettori (${esc(n.embedding)}). Diverso da quello che risponde.`],
      ["Database vettoriale", "Un archivio che conserva i vettori e trova i più vicini a una domanda. Qui è un file SQLite più una matrice in memoria."],
      ["Similarità del coseno", "Quanto due vettori puntano nella stessa direzione: 1 = stesso significato, 0 = niente in comune."],
      ["BM25", "La classica ricerca per parole dei motori di ricerca: conta le parole della domanda, premia quelle rare."],
      ["Ricerca ibrida", "Parole + significato insieme, fuse con la RRF."],
      ["RRF", "Reciprocal Rank Fusion: somma 1/(60+posizione) delle classifiche. Vince chi è in alto in tutte."],
      ["OCR", "Optical Character Recognition: leggere il testo da un'immagine (una pagina scansionata)."],
      ["Allucinazione", "Quando il modello inventa un'informazione plausibile ma falsa."],
      ["Prompt injection", "Istruzioni nascoste in un documento per manipolare il modello."],
      ["MCP", "Model Context Protocol: la presa standard con cui un programma (Unsloth Studio) usa gli strumenti di un altro (la ricerca di Archivio)."],
    ].map(([t, d]) => `<div class="voce"><b>${t}</b><span>${d}</span></div>`).join("")}
  </div>

  <h2 class="sotto">11 · Le domande che faranno in aula</h2>
  <div class="faq">
    <details open><summary>Allora è un database?</summary><p>Sì, nel senso che c'è un indice: un database con il testo dei pezzi, documento e pagina, e i vettori. Quando contiene vettori si chiama <b>database vettoriale</b> (<i>vector store</i>). Ma il RAG è tutto il percorso: leggere, tagliare, cercare, far rispondere, controllare. Il database ne è il magazzino.</p></details>
    <details><summary>Perché Unsloth Studio, con lo stesso modello, a volte risponde meglio?</summary><p>Con una cartella piccola, probabilmente fa leggere al modello tutti i documenti: il modello vede tutto e collega. Archivio adesso fa lo stesso in lettura automatica, quando l'archivio ci sta; e in più cita documento e pagina, controlla le citazioni e toglie gli ordini nascosti. Con un archivio grande nessuno dei due potrebbe leggere tutto: lì conta la qualità della ricerca.</p></details>
    <details><summary>I miei documenti escono dal computer?</summary><p>No, se scegli Ollama o LM Studio: tutto gira sul Mac, anche i vettori. Con OpenRouter le pagine scelte vanno al fornitore del modello in cloud, e Archivio lo ricorda con la fascia rossa fissa.</p></details>
    <details><summary>Perché a volte sbaglia?</summary><p>Tre motivi tipici: la ricerca non ha trovato la pagina giusta (si vede nel Laboratorio), l'OCR ha letto male una scansione (si vede nell'Indice), o il modello è troppo piccolo per collegare le informazioni. Per questo ogni risposta mostra le pagine lette: si può sempre controllare.</p></details>
    <details><summary>Se aggiungo un documento?</summary><p>Archivio se ne accorge da solo: lo legge, lo taglia, calcola i vettori, ed è subito interrogabile. Gli altri documenti non si toccano.</p></details>
    <details><summary>Serve un computer potente?</summary><p>I vettori e la ricerca sono leggeri. Quello che pesa è il modello che risponde: un 4B come Spark gira bene su un portatile recente con 16 GB; i 27–35B vogliono 32–48 GB.</p></details>
  </div>`;

  $("#calcola").addEventListener("click", calcolaVettori);
  calcolaVettori();
  try {
    const r = await api("/api/laboratorio/cerca", { metodo: "POST", dati: { domanda: A.stato?.domande_esempio?.[0] || "contratto" } });
    const tutto = r.messaggi[0].content + "\n\n────────\n\n" + r.messaggi[1].content;
    $("#msg-esempio").textContent = tutto.length > 2600 ? tutto.slice(0, 2600) + "\n\n[… continua con gli altri estratti e la domanda]" : tutto;
  } catch (e) { $("#msg-esempio").textContent = e.message; }
}

SEZIONI.rag = sezRag;
