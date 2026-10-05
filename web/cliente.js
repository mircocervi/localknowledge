// Archivio — pagina del cliente.

const S = {
  stato: null,
  scelta: { fornitore: "ollama", modello: "", ragionamento: false },
  modelli: {},
  fornitorePannello: null,
  dopo: Date.now() / 1000,
  aperte: new Set(),
  impronta: "",
  occupato: false,
};

$$("[data-icona]").forEach(el => (el.outerHTML = icona(el.dataset.icona)));

// ---------------- stato e cartelle ----------------

async function caricaStato() {
  let st;
  try { st = await api(`/api/stato?dopo=${S.dopo}`); }
  catch { $("#stato-indice").innerHTML = `<span class="pallino spento"></span> app non raggiungibile`; return; }
  const primo = !S.stato;
  S.stato = st;
  if (primo) {
    S.scelta = { ...st.scelta };
    $("#ragionamento").checked = !!S.scelta.ragionamento;
    $("#modo").value = S.scelta.modo || "auto";
    disegnaScelta();
    disegnaEsempi(st.domande_esempio);
    disegnaSchede(st.moduli);
  } else {
    disegnaSchede(st.moduli);
  }
  avvisiNuoviDocumenti(st.registro);
  if (st.registro.length) S.dopo = st.registro[st.registro.length - 1].t;
  const impronta = JSON.stringify([st.cartelle, st.indicizzazione]);
  if (impronta !== S.impronta) { S.impronta = impronta; disegnaCartelle(); }
  const i = st.indicizzazione;
  $("#stato-indice").innerHTML = i.attivo
    ? `<span class="pallino lavora"></span> indicizzo ${esc(i.file || "")}<span class="puntini"></span>`
    : `${numero(st.totale.documenti)} documenti · ${numero(st.totale.pezzi)} pezzi`;
}

function disegnaCartelle() {
  const st = S.stato, i = st.indicizzazione;
  $("#conto-cartelle").textContent = st.cartelle.length || "";
  const box = $("#cartelle");
  if (!st.cartelle.length) {
    box.innerHTML = `<p class="piccolo" style="margin:0 0 12px">Nessuna cartella. Aggiungi quella dei documenti da interrogare:
      l'app la legge e basta, gli originali non si toccano mai.</p>`;
    disegnaVuoto(true);
    return;
  }
  disegnaVuoto(false);
  box.innerHTML = st.cartelle.map(c => {
    const lavora = i.attivo && i.cartella === c.nome;
    const perc = lavora && i.totale ? Math.round((i.fatti / i.totale) * 100) : 0;
    return `<div class="cassetto ${c.attiva ? "" : "spento"}" data-id="${c.id}">
      <div class="riga1">
        <input type="checkbox" ${c.attiva ? "checked" : ""} data-azione="attiva" title="Cerca in questa cartella" aria-label="Cerca in ${esc(c.nome)}">
        <span class="nome" title="${esc(c.nome)}">${esc(c.nome)}</span>
        ${lavora ? '<span class="pallino lavora" title="Indicizzazione in corso"></span>' : c.esiste ? "" : '<span class="tag no">non trovata</span>'}
      </div>
      <div class="percorso">${esc(c.percorso)}</div>
      <div class="conti"><span><b>${numero(c.documenti)}</b> documenti</span><span><b>${numero(c.pagine)}</b> pagine</span>
        ${c.pagine_ocr ? `<span title="Pagine scansionate lette con l'OCR"><b>${c.pagine_ocr}</b> OCR</span>` : ""}
        ${c.errori ? `<span style="color:var(--timbro)"><b>${c.errori}</b> non letti</span>` : ""}</div>
      ${lavora ? `<div class="barra"><i style="width:${perc}%"></i></div><div class="fase">${esc(i.file || "")} · ${esc(i.fase || "")} (${i.fatti}/${i.totale})</div>` : ""}
      <div class="azioni">
        <button class="btn fantasma piccolo-btn" data-azione="elenco">${icona(S.aperte.has(c.id) ? "freccia_giu" : "doc")} ${S.aperte.has(c.id) ? "Chiudi" : "Documenti"}</button>
        <button class="btn fantasma piccolo-btn" data-azione="reindicizza" title="Rileggi tutti i documenti">${icona("aggiorna")}</button>
        <button class="btn fantasma piccolo-btn" data-azione="togli" title="Togli dall'archivio (i file restano dove sono)">${icona("cestino")}</button>
      </div>
      ${S.aperte.has(c.id) ? `<ul class="elenco-doc" data-elenco="${c.id}"><li class="piccolo">carico<span class="puntini"></span></li></ul>` : ""}
    </div>`;
  }).join("");
  S.aperte.forEach(id => caricaElenco(id));
}

async function caricaElenco(id) {
  const ul = $(`[data-elenco="${id}"]`);
  if (!ul) return;
  const docs = await api(`/api/documenti?cartella=${id}`);
  ul.innerHTML = docs.map(d => `<li>
      <a href="${linkDocumento(d.id, 1, d.nome)}" target="_blank" rel="noopener" title="${esc(d.nome)}">${esc(d.nome)}</a>
      ${d.errore ? '<span class="tag no" title="' + esc(d.errore) + '">errore</span>' : d.pagine_ocr ? '<span class="tag ocr">ocr</span>' : ""}
      <span class="piccolo">${d.pagine}</span></li>`).join("") || '<li class="piccolo">ancora vuota</li>';
}

$("#cartelle").addEventListener("click", async ev => {
  const b = ev.target.closest("[data-azione]");
  if (!b) return;
  const id = b.closest(".cassetto").dataset.id;
  const c = S.stato.cartelle.find(x => x.id === id);
  const az = b.dataset.azione;
  try {
    if (az === "attiva") {
      await api(`/api/cartelle/${id}`, { metodo: "PATCH", dati: { attiva: b.checked } });
    } else if (az === "elenco") {
      S.aperte.has(id) ? S.aperte.delete(id) : S.aperte.add(id);
      S.impronta = ""; disegnaCartelle();
      return;
    } else if (az === "reindicizza") {
      await api(`/api/cartelle/${id}/reindicizza`, { metodo: "POST" });
      biglietto(`${icona("aggiorna")}<div><b>Rileggo «${esc(c.nome)}»</b><div class="piccolo">Tutti i documenti, OCR compreso.</div></div>`);
    } else if (az === "togli") {
      if (!confirm(`Togliere «${c.nome}» dall'archivio?\n\nL'indice di questa cartella viene cancellato. I file originali restano dove sono.`)) return;
      await api(`/api/cartelle/${id}`, { metodo: "DELETE" });
    }
    caricaStato();
  } catch (e) { biglietto(`${icona("avviso")}<div><b>Non riuscito</b><div class="piccolo">${esc(e.message)}</div></div>`, { colore: "var(--timbro)" }); }
});

$("#aggiungi").addEventListener("click", async () => {
  const b = $("#aggiungi");
  b.disabled = true;
  b.innerHTML = `${icona("cartella")} Scegli nella finestra del Mac<span class="puntini"></span>`;
  try {
    const r = await api("/api/cartelle/scegli", { metodo: "POST" });
    if (r.percorso) await aggiungiCartella(r.percorso);
    else $("#a-mano").classList.remove("nascosto");
  } catch {
    $("#a-mano").classList.remove("nascosto");
  } finally {
    b.disabled = false;
    b.innerHTML = `${icona("piu")} Aggiungi cartella`;
  }
});
$("#aggiungi-percorso").addEventListener("click", () => aggiungiCartella($("#percorso").value));
$("#percorso").addEventListener("keydown", e => e.key === "Enter" && aggiungiCartella($("#percorso").value));

async function aggiungiCartella(percorso) {
  try {
    const c = await api("/api/cartelle", { metodo: "POST", dati: { percorso } });
    $("#percorso").value = "";
    $("#a-mano").classList.add("nascosto");
    biglietto(`${icona("cartella")}<div><b>Aggiunta «${esc(c.nome)}»</b><div class="piccolo">La leggo adesso: testo, OCR, pezzi e vettori.</div></div>`);
    caricaStato();
  } catch (e) {
    $("#a-mano").classList.remove("nascosto");
    biglietto(`${icona("avviso")}<div><b>Cartella non aggiunta</b><div class="piccolo">${esc(e.message)}</div></div>`, { colore: "var(--timbro)" });
  }
}

// Avvisi "nuovo documento": arrivano dall'osservatore delle cartelle
function avvisiNuoviDocumenti(registro) {
  const eventi = registro.filter(r => r.evento);
  if (!eventi.length) return;
  if (eventi.length > 3) {
    const nuovi = eventi.filter(e => e.evento.tipo === "nuovo").length;
    biglietto(`${icona("doc")}<div><b>${eventi.length} documenti indicizzati</b><div class="piccolo">${nuovi} nuovi · ${esc(eventi[0].evento.cartella)}</div></div>`);
    return;
  }
  for (const r of eventi) {
    const e = r.evento;
    if (e.tipo === "rimosso") {
      biglietto(`${icona("cestino")}<div><b>Tolto dall'indice</b><div class="piccolo">${esc(e.nome)} non è più nella cartella</div></div>`, { colore: "var(--grigio)" });
    } else {
      biglietto(`${icona("doc")}<div><b>${e.tipo === "nuovo" ? "Nuovo documento" : "Documento aggiornato"}: indicizzato</b>
        <div class="piccolo">${esc(e.nome)} · ${e.pagine} ${e.pagine === 1 ? "pagina" : "pagine"}${e.ocr ? ` · ${e.ocr} con OCR` : ""} · ${e.pezzi} pezzi</div></div>`, { durata: 8000 });
    }
  }
}

// ---------------- servizi (pallini nel lato) ----------------

async function controllaServizi() {
  const [o, l] = await Promise.all([api("/api/modelli/ollama").catch(() => ({})), api("/api/modelli/lmstudio").catch(() => ({}))]);
  S.modelli.ollama = o; S.modelli.lmstudio = l;
  const or = S.stato?.openrouter_chiave;
  $("#servizi").innerHTML = `
    <div><span class="pallino ${o.acceso ? "acceso" : "spento"}"></span> Ollama ${o.acceso ? `· ${o.modelli.length} modelli` : "spento"}</div>
    <div><span class="pallino ${l.acceso ? "acceso" : "spento"}"></span> LM Studio ${l.acceso ? `· ${l.modelli.length} modelli` : "spento"}</div>
    <div><span class="pallino ${or ? "acceso" : ""}"></span> OpenRouter ${or ? "· chiave presente" : "· nessuna chiave"}</div>
    <div class="piccolo" style="margin-top:6px">${icona("lucchetto")} Vettori sempre in locale</div>`;
  disegnaScelta();
}

// ---------------- scelta del modello ----------------

function disegnaScelta() {
  const f = S.scelta.fornitore, st = S.stato;
  if (!st) return;
  $("#forn-nome").textContent = st.fornitori[f]?.nome || f;
  $("#mod-nome").textContent = S.scelta.modello ? nomeModello(S.scelta.modello) : "scegli un modello";
  $("#mod-nome").title = S.scelta.modello || "";
  const e = S.modelli[f];
  const pronto = e && e.acceso && (f !== "openrouter" || st.openrouter_chiave);
  $("#pallino-modello").className = "pallino " + (e ? (pronto ? "acceso" : "spento") : "");
  $("#pallino-modello").title = f === "openrouter" && !st.openrouter_chiave ? "Manca la chiave OPENROUTER_API_KEY" : "";
  $("#fascia").innerHTML = f === "openrouter"
    ? `<div class="fascia-uscita" role="alert">${icona("uscita")} Gli estratti dei documenti escono dal computer</div>` : "";
}

function apriPannello(aperto) {
  const p = $("#pannello-modello");
  p.classList.toggle("nascosto", !aperto);
  $("#apri-modello").setAttribute("aria-expanded", aperto);
  if (aperto) mostraFornitore(S.scelta.fornitore);
}
$("#apri-modello").addEventListener("click", e => { e.stopPropagation(); apriPannello($("#pannello-modello").classList.contains("nascosto")); });
document.addEventListener("click", e => {
  // un elemento appena ridisegnato non è più nel documento: il clic era comunque dentro il pannello
  if (!e.target.isConnected || e.target.closest("#pannello-modello")) return;
  apriPannello(false);
});
document.addEventListener("keydown", e => { if (e.key === "Escape") apriPannello(false); });

async function mostraFornitore(f) {
  S.fornitorePannello = f;
  const st = S.stato;
  $("#segmenti").innerHTML = Object.entries(st.fornitori).map(([k, v]) =>
    `<button data-f="${k}" aria-pressed="${k === f}">${v.locale ? icona("lucchetto") : icona("uscita")} ${esc(v.nome)}</button>`).join("");
  $("#nota-fornitore").innerHTML = f === "openrouter"
    ? `<div class="nota errore">${icona("uscita")}<div><b>Gli estratti dei documenti escono dal computer.</b> Vanno a OpenRouter e al fornitore del modello.
        ${st.openrouter_chiave ? "" : "<br>Manca la chiave: imposta <span class='mono'>OPENROUTER_API_KEY</span> e riavvia l'app."}</div></div>`
    : `<div class="piccolo">${icona("lucchetto")} ${esc(st.fornitori[f].nome)} gira su questo Mac: <span class="mono">${esc(st.fornitori[f].url)}</span></div>`;
  $("#filtro-modelli").classList.toggle("nascosto", f !== "openrouter");
  $("#lista-modelli").innerHTML = `<div style="padding:14px" class="piccolo">Chiedo l'elenco a ${esc(st.fornitori[f].nome)}<span class="puntini"></span></div>`;
  if (!S.modelli[f] || f === "openrouter" || !S.modelli[f].acceso) S.modelli[f] = await api(`/api/modelli/${f}`).catch(e => ({ acceso: false, errore: e.message }));
  if (S.fornitorePannello === f) disegnaListaModelli();
}
$("#segmenti").addEventListener("click", async e => {
  const b = e.target.closest("[data-f]");
  if (!b) return;
  const f = b.dataset.f, pref = S.stato.preferiti?.[f];
  if (pref && f !== S.scelta.fornitore) {
    S.scelta.fornitore = f; S.scelta.modello = pref;
    await api("/api/scelta", { metodo: "POST", dati: S.scelta });
    disegnaScelta();
    scalda();
  }
  mostraFornitore(f);
});
$("#filtro-modelli").addEventListener("input", disegnaListaModelli);

function disegnaListaModelli() {
  const f = S.fornitorePannello, e = S.modelli[f];
  if (!e.acceso) {
    $("#lista-modelli").innerHTML = `<div class="nota attenzione" style="margin:10px">${icona("avviso")}<div>${esc(e.errore || "Spento")}</div></div>`;
    return;
  }
  const q = $("#filtro-modelli").value.toLowerCase();
  let lista = e.modelli.filter(m => !q || m.id.toLowerCase().includes(q) || (m.nome || "").toLowerCase().includes(q));
  // il modello scelto (o il preferito) sempre in cima
  const inCima = S.scelta.fornitore === f ? S.scelta.modello : S.stato.preferiti?.[f];
  lista.sort((a, b) => (b.id === inCima) - (a.id === inCima));
  const totale = lista.length;
  if (f === "openrouter") lista = lista.slice(0, 120);
  $("#lista-modelli").innerHTML = lista.map(m => {
    const meta = [m.parametri, m.quantizzazione, m.dimensione ? byte(m.dimensione) : "", m.tipo === "vlm" ? "vede immagini" : "",
      m.caricato ? "in memoria" : "", m.gratis ? "gratis" : "", m.contesto ? `${Math.round(m.contesto / 1000)}k contesto` : ""].filter(Boolean).join(" · ");
    const sel = S.scelta.fornitore === f && S.scelta.modello === m.id;
    return `<button data-m="${esc(m.id)}" aria-selected="${sel}">${sel ? icona("spunta") : '<span style="width:16px"></span>'}<span class="id">${esc(m.id)}</span><span class="meta">${esc(meta)}</span></button>`;
  }).join("") + (totale > lista.length ? `<div class="piccolo" style="padding:10px 12px">… altri ${totale - lista.length}: affina la ricerca</div>` : "")
    || `<div class="piccolo" style="padding:14px">Nessun modello.</div>`;
}
$("#lista-modelli").addEventListener("click", async e => {
  const b = e.target.closest("[data-m]");
  if (!b) return;
  S.scelta.fornitore = S.fornitorePannello;
  S.scelta.modello = b.dataset.m;
  await api("/api/scelta", { metodo: "POST", dati: S.scelta });
  disegnaScelta();
  apriPannello(false);
  scalda();
});
$("#modo").addEventListener("change", e => {
  S.scelta.modo = e.target.value;
  api("/api/scelta", { metodo: "POST", dati: { modo: S.scelta.modo } });
});
$("#ragionamento").addEventListener("change", e => {
  S.scelta.ragionamento = e.target.checked;
  api("/api/scelta", { metodo: "POST", dati: { ragionamento: S.scelta.ragionamento } });
});

// Carica il modello in memoria subito, così la prima risposta non aspetta
async function scalda() {
  if (!S.scelta.modello || S.scelta.fornitore === "openrouter") return;
  const p = $("#pallino-modello");
  p.className = "pallino lavora"; p.title = "Carico il modello in memoria…";
  const r = await api("/api/scalda", { metodo: "POST", dati: S.scelta }).catch(e => ({ ok: false, errore: e.message }));
  p.className = "pallino " + (r.ok ? "acceso" : "spento");
  p.title = r.ok ? `Pronto (caricato in ${secondi(r.secondi)})` : r.errore;
}

// ---------------- domande ----------------

function disegnaEsempi(esempi) {
  $("#esempi").innerHTML = (esempi || []).map(q => `<button>${esc(q)}</button>`).join("");
}
$("#esempi").addEventListener("click", e => {
  const b = e.target.closest("button");
  if (!b) return;
  $("#domanda").value = b.textContent;
  chiedi();
});
$("#domanda").addEventListener("keydown", e => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey || !e.shiftKey)) { e.preventDefault(); chiedi(); }
});
$("#domanda").addEventListener("input", e => { e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 240) + "px"; });
$("#invia").addEventListener("click", () => (S.occupato ? fermaRisposta() : chiedi()));

// ---------------- freno e spegnimento del motore ----------------

const ETICHETTA_INVIA = () => `Chiedi ${icona("invia")}`;
function modoInvio(occupato) {
  const b = $("#invia");
  b.disabled = false;
  b.classList.toggle("rosso", occupato);
  b.classList.toggle("pieno", !occupato);
  b.innerHTML = occupato ? `${icona("croce")} Ferma` : ETICHETTA_INVIA();
  b.title = occupato ? "Ferma la risposta: il modello smette di lavorare" : "";
}
async function fermaRisposta() {
  S.controllo?.abort();
  await api("/api/ferma", { metodo: "POST" }).catch(() => {});
}
async function spegniMotore() {
  const b = $("#spegni");
  b.disabled = true;
  b.innerHTML = `${icona("spina")} Spengo<span class="puntini"></span>`;
  S.controllo?.abort();
  try {
    const r = await api("/api/motore/spegni", { metodo: "POST" });
    biglietto(`${icona("spina")}<div><b>Motore spento</b><div class="piccolo">${r.tolti.length ? "Tolti dalla memoria: " + r.tolti.map(esc).join(", ") : "Nessun modello era in memoria."}
      Alla prossima domanda il modello si ricarica da solo.</div></div>`, { durata: 9000, colore: "var(--ocra)" });
  } catch (e) { biglietto(`${icona("avviso")}<div><b>Non riuscito</b><div class="piccolo">${esc(e.message)}</div></div>`, { colore: "var(--timbro)" }); }
  b.disabled = false;
  aggiornaMotore();
}
async function aggiornaMotore() {
  const m = await api("/api/motore").catch(() => null);
  if (!m) return;
  const b = $("#spegni");
  const n = m.in_memoria.length;
  b.innerHTML = `${icona("spina")} ${n ? `Spegni il motore · ${n} ${n === 1 ? "modello" : "modelli"} in memoria` : "Motore a riposo"}`;
  b.title = n ? m.in_memoria.join("\n") : "Nessun modello in memoria";
  b.classList.toggle("caldo", n > 0);
}

function disegnaVuoto(vuoto) {
  const r = $("#risposte");
  if (vuoto && !r.children.length) {
    r.innerHTML = `<div class="vuoto" id="vuoto">${icona("cartella", "").replace('class="icona', 'style="width:46px;height:46px;stroke-width:1.2" class="icona')}
      <div class="titolo">Prima, una cartella</div>
      <p>Scegli la cartella con i documenti (PDF, Word, testo, Markdown, CSV). L'app li legge, fa l'OCR delle scansioni e li prepara per le domande.</p>
      <button class="btn pieno" onclick="$('#aggiungi').click()">${icona("piu")} Aggiungi cartella</button></div>`;
  } else if (!vuoto) $("#vuoto")?.remove();
}

async function chiedi() {
  const domanda = $("#domanda").value.trim();
  if (!domanda || S.occupato) return;
  S.controllo = new AbortController();
  if (!S.scelta.modello) { apriPannello(true); return; }
  S.occupato = true;
  modoInvio(true);
  $("#domanda").value = "";
  $("#domanda").style.height = "auto";
  $("#vuoto")?.remove();
  const card = document.createElement("article");
  card.className = "carta risposta";
  const nomeF = S.stato.fornitori[S.scelta.fornitore].nome;
  const locale = S.stato.fornitori[S.scelta.fornitore].locale;
  card.innerHTML = `
    <h3 class="chiesta">${esc(domanda)}</h3>
    <div class="chi"><span class="tag ${locale ? "ok" : "no"}">${locale ? "locale" : "esterno"}</span> ${esc(nomeF)} · <span class="mono" title="${esc(S.scelta.modello)}">${esc(nomeModello(S.scelta.modello))}</span>
      ${S.scelta.ragionamento ? `<span class="tag neutro">${icona("cervello")} ragiona</span>` : ""}</div>
    <div class="lettura piccolo nascosto"></div>
    <div class="testo cursore"><p class="piccolo">Preparo il modello e i documenti<span class="puntini"></span></p></div>
    <div class="verifica"></div><div class="blocco-versioni"></div>
    <details class="ragion nascosto"><summary>${icona("cervello")} Ragionamento del modello</summary><pre></pre></details>
    <div class="tempi"></div>
    <div class="estratti-titolo nascosto"></div><div class="estratti"></div>`;
  $("#risposte").prepend(card);
  card.scrollIntoView({ behavior: "smooth", block: "nearest" });

  let estratti = [], testo = "", ragion = "", tempiRicerca = null, disegnoInAttesa = false;
  const elTesto = $(".testo", card);
  const ridisegna = () => {
    if (disegnoInAttesa) return;
    disegnoInAttesa = true;
    requestAnimationFrame(() => { disegnoInAttesa = false; elTesto.innerHTML = rendiRisposta(testo, estratti) || "<p></p>"; });
  };
  try {
    const r = await fetch("/api/chiedi", {
      method: "POST", headers: { "Content-Type": "application/json" }, signal: S.controllo.signal,
      body: JSON.stringify({ domanda, ...S.scelta }),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Errore ${r.status}`);
    const lettore = r.body.getReader(), dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await lettore.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) !== -1) {
        const blocco = buf.slice(0, i); buf = buf.slice(i + 2);
        const ev = (blocco.match(/^event: (.*)$/m) || [])[1];
        const dati = JSON.parse((blocco.match(/^data: (.*)$/m) || [])[1] || "{}");
        if (ev === "fase") {
          if (!testo) elTesto.innerHTML = `<p class="piccolo">${esc(dati.t)}<span class="puntini"></span></p>`;
        } else if (ev === "estratti") {
          estratti = dati.estratti; tempiRicerca = dati.tempi;
          card._modo = dati.modo;
          disegnaLettura(card, dati);
          disegnaEstratti(card, estratti, domanda, dati.modo === "tutto" ? [] : null);
          card._versioni = dati.versioni;
          if (dati.avviso) $(".verifica", card).innerHTML = `<div class="nota attenzione">${icona("avviso")}<div>${esc(dati.avviso)}</div></div>`;
          elTesto.innerHTML = `<p class="piccolo">${dati.modo === "tutto" ? `Il modello legge tutto l'archivio: ${estratti.length} pagine` : `Il modello legge ${estratti.length} pagine trovate dalla ricerca`}<span class="puntini"></span></p>`;
          setTimeout(() => { if (!testo && !ragion && card.isConnected && !$(".nota-avvio", card)) elTesto.insertAdjacentHTML("beforeend",
            `<p class="piccolo nota-avvio">Se il modello non era in memoria, il primo avvio richiede qualche secondo per caricarlo.</p>`); }, 5000);
        } else if (ev === "ragionamento") {
          ragion += dati.t;
          const d = $("details.ragion", card); d.classList.remove("nascosto");
          $("pre", d).textContent = ragion;
          if (!testo) elTesto.innerHTML = `<p class="piccolo">${icona("cervello")} Il modello ragiona<span class="puntini"></span></p>`;
        } else if (ev === "testo") {
          testo += dati.t; ridisegna();
        } else if (ev === "fine") {
          concludi(card, testo, estratti, dati, tempiRicerca);
        } else if (ev === "errore") {
          throw new Error(dati.messaggio);
        }
      }
    }
  } catch (e) {
    elTesto.classList.remove("cursore");
    if (e.name === "AbortError") {
      if (testo) { elTesto.innerHTML = rendiRisposta(testo, estratti); }
      elTesto.insertAdjacentHTML(testo ? "beforeend" : "afterbegin", `<p class="tag neutro" style="margin-top:8px">${icona("croce")} fermata da te</p>`);
      if (!testo) elTesto.querySelectorAll("p.piccolo").forEach(x => x.remove());
      return;
    }
    elTesto.innerHTML = `<div class="nota errore">${icona("avviso")}<div><b>Nessuna risposta.</b> ${esc(e.message)}</div></div>`;
  } finally {
    elTesto.classList.remove("cursore");
    S.occupato = false;
    S.controllo = null;
    modoInvio(false);
    setTimeout(aggiornaMotore, 800);
  }
}

function concludi(card, testo, estratti, dati, tempiRicerca) {
  const v = dati.verifica, st = dati.statistiche || {};
  const elTesto = $(".testo", card);
  if (v.non_presente) {
    elTesto.innerHTML = `<div class="timbro-np">Non presente nei documenti</div>`;
  } else if (!testo) {
    elTesto.innerHTML = `<div class="nota attenzione">${icona("avviso")}<div>Il modello non ha scritto la risposta${st.troncata ? ": ha esaurito i token mentre ragionava. Riprova senza «Ragionamento»." : "."}</div></div>`;
  } else {
    elTesto.innerHTML = rendiRisposta(testo, estratti);
  }
  const chip = [];
  if (v.non_presente) chip.push(`<span class="tag neutro">${icona("spunta")} Nessuna invenzione: l'informazione non c'è</span>`);
  if (v.citati.length) chip.push(`<span class="tag ok" title="Ogni citazione corrisponde a un estratto davvero passato al modello">${icona("spunta")} ${v.citati.length} ${v.citati.length === 1 ? "citazione verificata" : "citazioni verificate"}</span>`);
  if (v.inventate.length) chip.push(`<span class="tag no">${icona("croce")} Citazioni inesistenti: ${v.inventate.map(n => "E" + n).join(", ")}</span>`);
  if (v.frasi_senza_citazione.length) chip.push(`<span class="tag ocr" title="${esc(v.frasi_senza_citazione.join("\n\n"))}">${icona("avviso")} ${v.frasi_senza_citazione.length} ${v.frasi_senza_citazione.length === 1 ? "frase" : "frasi"} senza citazione</span>`);
  if (!v.non_presente && testo && !v.citati.length) chip.push(`<span class="tag no">${icona("avviso")} Risposta senza citazioni: non verificabile</span>`);
  if (v.istruzioni_ignorate?.length) {
    $(".verifica", card).insertAdjacentHTML("afterend", `<div class="nota errore" style="margin-top:14px">${icona("avviso")}<div>
      <b>Istruzioni nascoste ignorate.</b> ${v.istruzioni_ignorate.map(x => `<b>${esc(nomeBreve(x.nome))}</b> (${unitaBreve(estratti[x.n - 1]?.unita)} ${x.pagina}) contiene frasi che danno ordini a un'AI:
      ${x.frasi.map(f => `<i>«${esc(f.length > 180 ? f.slice(0, 180) + "…" : f)}»</i>`).join(" ")}`).join("<br>")}
      <div class="piccolo" style="margin-top:4px">L'app le ha tolte dagli estratti prima che arrivassero al modello: sono dati, non istruzioni.</div></div></div>`);
  }
  if (st.troncata && testo) chip.push(`<span class="tag ocr">risposta interrotta (limite token)</span>`);
  if (st.interrotta) chip.push(`<span class="tag no" title="Il server del modello ha chiuso la connessione prima della fine">${icona("avviso")} risposta interrotta: riprova</span>`);
  $(".verifica", card).insertAdjacentHTML("beforeend", chip.join(""));
  if (card._modo === "tutto") disegnaEstratti(card, estratti, $(".chiesta", card).textContent, v.citati);
  $$(".schedina", card).forEach(s => s.classList.toggle("citata", v.citati.includes(+s.dataset.n)));
  disegnaVersioni(card, card._versioni, v.citati.map(n => estratti[n - 1]?.nome), card._modo === "tutto");
  const tr = tempiRicerca || {};
  $(".tempi", card).innerHTML = `
    <span>${icona("orologio")} Modello <b>${secondi(st.secondi)}</b></span>
    <span>Primo token <b>${secondi(st.primo_token)}</b></span>
    ${st.token ? `<span><b>${numero(st.token)}</b> token${st.token_al_secondo ? ` · <b>${String(st.token_al_secondo).replace(".", ",")}</b>/s` : ""}</span>` : ""}
    ${card._modo === "tutto" ? "" : `<span>${icona("lente")} Ricerca <b>${(tr.vettore_domanda_ms || 0) + (tr.ricerca_ms || 0)} ms</b></span>`}`;
  // passando sopra una citazione si illumina la sua scheda
  $$(".cit[data-e]", card).forEach(c => {
    const s = $(`.schedina[data-n="${c.dataset.e}"]`, card);
    c.addEventListener("mouseenter", () => s && (s.style.transform = "translateY(-3px)", s.style.boxShadow = "var(--ombra-alta)"));
    c.addEventListener("mouseleave", () => s && (s.style.transform = "", s.style.boxShadow = ""));
  });
}

function disegnaLettura(card, d) {
  const el = $(".lettura", card);
  el.classList.remove("nascosto");
  const tok = d.token_documenti ? `circa ${numero(d.token_documenti)} token` : "";
  const ctx = d.contesto ? `memoria di lavoro del modello ${numero(d.contesto)} token` : "";
  el.innerHTML = d.modo === "tutto"
    ? `<span class="tag ok" title="L'archivio entra tutto nel contesto del modello: niente ricerca, legge ogni pagina">${icona("doc")} tutto l'archivio · senza RAG</span>
       ${d.estratti.length} pagine di ${d.documenti} documenti · ${tok} · ${ctx}`
    : `<span class="tag neutro" title="Ricerca ibrida (RAG): solo le pagine più pertinenti arrivano al modello">${icona("lente")} RAG · ricerca</span>
       ${d.estratti.length} pagine di ${d.documenti} documenti · ${tok} · ${ctx}`;
}

function disegnaEstratti(card, estratti, domanda, soloQuesti = null) {
  // soloQuesti: in "tutto l'archivio" si mostrano le pagine citate; le altre con un clic
  const t = $(".estratti-titolo", card);
  const mostra = soloQuesti === null ? estratti.map((_, i) => i + 1) : soloQuesti;
  const altre = estratti.length - mostra.length;
  if (soloQuesti !== null && !mostra.length) { t.classList.add("nascosto"); $(".estratti", card).innerHTML = ""; }
  else {
    t.classList.remove("nascosto");
    t.textContent = soloQuesti === null ? `Pagine lette dal modello · ${estratti.length}` : `Pagine citate · ${mostra.length} su ${estratti.length} lette`;
  }
  $(".estratti", card).innerHTML = mostra.map(n => {
    const e = estratti[n - 1];
    if (!e) return "";
    return `
    <div class="schedina" data-n="${n}">
      <div class="testa"><span class="n">E${n}</span>
        <a class="doc" href="${linkDocumento(e.doc_id, e.pagina, e.nome)}" target="_blank" rel="noopener" title="Apri ${esc(e.nome)} alla ${e.unita} ${e.pagina}">${esc(e.nome)}</a>
        <span class="pag">${unitaBreve(e.unita)} ${e.pagina}</span>${e.ocr ? '<span class="tag ocr" title="Pagina scansionata, letta con l\'OCR">ocr</span>' : ""}</div>
      <div class="brano">${evidenzia(e.testo, domanda)}</div>
      ${e.rango_parole || e.rango_significato ? `<div class="ranghi" title="Posizione nelle due classifiche della ricerca ibrida">
        <i class="rp">parole ${e.rango_parole ? "#" + e.rango_parole : "—"}</i><i class="rs">significato ${e.rango_significato ? "#" + e.rango_significato : "—"}</i></div>` : ""}
    </div>`;
  }).join("") + (soloQuesti !== null && altre > 0
    ? `<button class="btn fantasma piccolo-btn" data-tutte style="justify-self:start">${icona("doc")} Mostra tutte le ${estratti.length} pagine lette</button>` : "");
  $$(".schedina .brano", card).forEach(b => b.addEventListener("click", () => b.parentElement.classList.toggle("aperta")));
  const bt = $("[data-tutte]", card);
  if (bt) bt.onclick = () => {
    const citate = soloQuesti;
    disegnaEstratti(card, estratti, domanda, null);
    $$(".schedina", card).forEach(s => s.classList.toggle("citata", citate.includes(+s.dataset.n)));
  };
}

function disegnaVersioni(card, avvisi, citati, tutto = false) {
  const utili = (avvisi || []).filter(a => a.tipo !== "solo_recente");
  const nomiCitati = new Set(citati || []);
  const toccaCitati = a => a.versioni.some(v => nomiCitati.has(v.nome));
  const forti = utili.filter(toccaCitati), deboli = tutto ? [] : utili.filter(a => !toccaCitati(a));
  const blocco = a => {
    const titolo = a.tipo === "manca_recente" ? "Attenzione: esiste una versione più recente" : "Più versioni dello stesso documento";
    return `<div class="versioni">
      <h4>${icona("versioni")} ${titolo}</h4>
      <ol>${a.versioni.map(v => `<li><a class="v ${v.negli_estratti ? "" : "assente"} ${v.nome === a.piu_recente ? "recente" : ""}" ${v.doc_id ? `href="${linkDocumento(v.doc_id, 1, v.nome)}" target="_blank" rel="noopener"` : ""} title="${v.negli_estratti ? "Tra gli estratti" : "Nell'archivio, ma non tra gli estratti"}" style="text-decoration:none;color:inherit">${esc(nomeBreve(v.nome))}</a></li>`).join("")}</ol>
      <p>La più recente è <b>${esc(a.piu_recente)}</b>${a.tipo === "manca_recente" ? ", ma non è tra gli estratti usati: verifica che la risposta valga ancora." : "."}${nomiCitati.has(a.piu_recente) ? " La risposta cita proprio questa." : ""}</p>
    </div>`;
  };
  $(".blocco-versioni", card).innerHTML = forti.map(blocco).join("") + (deboli.length ? `<p class="piccolo" style="margin:12px 0 0">${icona("versioni")}
    Tra gli estratti ci sono anche documenti in più versioni: ${deboli.map(a => `${esc(nomeBreve(a.piu_recente))} è la più recente di ${a.versioni.length}`).join(" · ")}.</p>` : "");
}

// ---------------- schede (moduli) ----------------

function disegnaSchede(moduli) {
  const bi = (moduli || []).find(m => m.id === "bi");
  const nav = $("#schede");
  const c = $('[data-scheda="bi"]', nav);
  if (bi?.acceso && !c) nav.insertAdjacentHTML("beforeend", `<a href="#bi" data-scheda="bi">${icona("grafico")} BI</a>`);
  if (!bi?.acceso && c) { c.remove(); if (location.hash === "#bi") location.hash = ""; }
  instrada();
}
function instrada() {
  const bi = location.hash === "#bi" && $('[data-scheda="bi"]');
  $("#vista-documenti").classList.toggle("nascosto", !!bi);
  $("#vista-bi").classList.toggle("nascosto", !bi);
  $$("#schede a").forEach(a => a.toggleAttribute("aria-current", (a.dataset.scheda === "bi") === !!bi));
  $$("#schede a[aria-current]").forEach(a => a.setAttribute("aria-current", "page"));
}
window.addEventListener("hashchange", instrada);

// ---------------- avvio ----------------

(async () => {
  await caricaStato();
  controllaServizi();
  scalda().then(aggiornaMotore);
  setInterval(aggiornaMotore, 10000);
  $("#spegni").addEventListener("click", spegniMotore);
  setInterval(caricaStato, 2000);
  setInterval(controllaServizi, 15000);
  $("#domanda").focus();
})();
