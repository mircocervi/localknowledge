// Archivio — funzioni condivise da cliente e admin.

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(percorso, { metodo = "GET", dati } = {}) {
  const r = await fetch(percorso, {
    method: metodo,
    headers: dati !== undefined ? { "Content-Type": "application/json" } : {},
    body: dati !== undefined ? JSON.stringify(dati) : undefined,
  });
  let j = null;
  try { j = await r.json(); } catch { /* risposta vuota */ }
  if (!r.ok) throw new Error((j && (j.detail || j.messaggio)) || `Errore ${r.status}`);
  return j;
}

// Icone disegnate a tratto (stile "penna"), 24x24.
const ICONE = {
  cartella: '<path d="M3 7.5A1.5 1.5 0 0 1 4.5 6h4l2 2h9A1.5 1.5 0 0 1 21 9.5v8a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z"/>',
  piu: '<path d="M12 5v14M5 12h14"/>',
  invia: '<path d="M4 12h14M13 6l6 6-6 6"/>',
  aggiorna: '<path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v4h-4"/>',
  cestino: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12h10l1-12M9 7V4h6v3"/>',
  occhio: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  avviso: '<path d="M12 3 2 20h20L12 3z"/><path d="M12 10v4M12 17v.01"/>',
  uscita: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  doc: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
  spunta: '<path d="m5 12 4.5 4.5L19 7"/>',
  croce: '<path d="M6 6l12 12M18 6 6 18"/>',
  versioni: '<path d="M8 4h9l3 3v11"/><path d="M4 8h9l3 3v9H4z"/>',
  chip: '<rect x="6" y="6" width="12" height="12" rx="1.5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  lucchetto: '<rect x="5" y="11" width="14" height="10" rx="1.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  copia: '<rect x="8" y="8" width="12" height="12" rx="1.5"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
  cervello: '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 1V5a2 2 0 0 0-3-1zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 1"/>',
  orologio: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  lente: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  freccia_giu: '<path d="m6 9 6 6 6-6"/>',
  spina: '<path d="M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0zM12 16v5"/>',
  grafico: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  stampa: '<path d="M7 9V3h10v6M7 17H5a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-2"/><path d="M7 14h10v7H7z"/>',
};
function icona(nome, classe = "") {
  return `<svg class="icona ${classe}" viewBox="0 0 24 24" aria-hidden="true">${ICONE[nome] || ""}</svg>`;
}

// "13_Rinnovo_Nordwand_2024.pdf" -> "Rinnovo Nordwand 2024"
function nomeBreve(nome) {
  return String(nome).replace(/\.[a-z0-9]+$/i, "").replace(/^\d{1,3}[_\-\s]+/, "").replace(/[_]+/g, " ");
}
function linkDocumento(doc_id, pagina, nome) {
  const pdf = /\.pdf$/i.test(nome || "");
  return pdf ? `/documento/${doc_id}#page=${pagina}` : `/documento/${doc_id}/testo#p${pagina}`;
}
// "hf.co/XHToken/Spark-X2.5-4B-GGUF:Q8_0" -> "Spark-X2.5-4B · Q8_0"
function nomeModello(id) {
  let s = String(id || "").replace(/^hf\.co\//, "");
  s = s.split("/").pop();
  const [base, tag] = s.split(":");
  return base.replace(/-GGUF$/i, "") + (tag && tag !== "latest" ? " · " + tag : "");
}
function unitaBreve(unita) { return unita === "sezione" ? "sez." : "p."; }

function secondi(s) {
  if (s == null) return "—";
  return s < 10 ? s.toFixed(1).replace(".", ",") + " s" : Math.round(s) + " s";
}
function byte(n) {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"]; let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i ? n.toFixed(1).replace(".", ",") : n) + " " + u[i];
}
function ora(t) { return new Date(t * 1000).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", second: "2-digit" }); }
function numero(n) { return (n ?? 0).toLocaleString("it-IT"); }

// Avvisi a comparsa in basso a destra
function biglietto(html, { durata = 6000, colore } = {}) {
  let v = $(".vassoio");
  if (!v) { v = document.createElement("div"); v.className = "vassoio"; v.setAttribute("aria-live", "polite"); document.body.append(v); }
  const b = document.createElement("div");
  b.className = "biglietto";
  if (colore) b.style.borderLeftColor = colore;
  b.innerHTML = html;
  v.append(b);
  setTimeout(() => { b.classList.add("via"); setTimeout(() => b.remove(), 320); }, durata);
}

// Testo della risposta -> HTML con le citazioni [E1] trasformate in etichette di documento e pagina
function rendiRisposta(testo, estratti) {
  let h = esc(testo);
  h = h.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/(\[\s*E\s*\d+(?:\s*[,;]\s*E?\s*\d+)*\s*\])+/gi, gruppo => {
    const numeri = [...new Set((gruppo.match(/\d+/g) || []).map(Number))];
    return numeri.map(n => {
      const e = estratti[n - 1];
      if (!e) return `<span class="cit inventata" title="Citazione inesistente: non c'è un estratto E${n}">E${n}?</span>`;
      const href = linkDocumento(e.doc_id, e.pagina, e.nome), dove = `${unitaBreve(e.unita)} ${e.pagina}`;
      return `<a class="cit" href="${href}" target="_blank" rel="noopener" data-e="${n}" title="${esc(e.nome)} · ${dove}"><span class="cit-n">E${n}</span>${esc(nomeBreve(e.nome))} · ${dove.replace(" ", "&nbsp;")}</a>`;
    }).join("");
  });
  return h.split(/\n{2,}/).map(p => `<p>${p.replace(/\n/g, "<br>")}</p>`).join("");
}

// Evidenzia nel testo le parole della domanda (radice grezza)
function evidenzia(testo, domanda) {
  const vuote = new Set("il lo la i gli le un una di da in con su per tra fra che cosa ci sono del della dei delle al alla se e o è".split(" "));
  const radici = (domanda.toLowerCase().match(/[\p{L}\d]+/gu) || [])
    .filter(w => w.length > 2 && !vuote.has(w)).map(w => w.length >= 7 ? w.slice(0, -2) : w.length >= 5 ? w.slice(0, -1) : w);
  let h = esc(testo);
  if (!radici.length) return h;
  const re = new RegExp(`(?<![\\p{L}\\d])(${[...new Set(radici)].map(r => r.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})[\\p{L}\\d]*`, "giu");
  return h.replace(re, m => `<mark>${m}</mark>`);
}

function copia(testo, bottone) {
  navigator.clipboard.writeText(testo).then(() => {
    if (!bottone) return;
    const prima = bottone.innerHTML;
    bottone.innerHTML = icona("spunta") + " Copiato";
    setTimeout(() => (bottone.innerHTML = prima), 1400);
  });
}
