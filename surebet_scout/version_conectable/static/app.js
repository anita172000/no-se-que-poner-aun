"use strict";
// ---------- utilidades ----------
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const nf2 = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const eur = (n) => (n == null || isNaN(n) ? "—" : nf2.format(n) + " €");
const pct = (n) => nf2.format(n * 100) + " %";
const signed = (n) => `<span class="num ${n >= 0 ? "pos" : "neg"}">${n >= 0 ? "+" : ""}${eur(n)}</span>`;
const fdate = (iso) => (iso ? new Date(iso).toLocaleString("es-ES", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "");
const ago = (iso) => { if (!iso) return ""; const s = Math.round((Date.now() - new Date(iso)) / 1000); return s < 60 ? `hace ${s} s` : `hace ${Math.round(s / 60)} min`; };
const SPORTS_ES = {
  football: "Fútbol", tennis: "Tenis", basketball: "Baloncesto", "ice-hockey": "Hockey hielo",
  esports: "Esports", baseball: "Béisbol", "american-football": "Fútbol americano", handball: "Balonmano",
  volleyball: "Voleibol", rugby: "Rugby", cricket: "Críquet", darts: "Dardos", snooker: "Snooker",
  "table-tennis": "Tenis de mesa", boxing: "Boxeo", "mixed-martial-arts": "MMA", badminton: "Bádminton",
  "aussie-rules": "Fútbol australiano",
};
const STATE_BADGE = { abierta: "blue", "en curso": "amber", completa: "", expuesta: "red", liquidada: "grey", cancelada: "grey" };
const evName = (o) => esc(o.home) + (o.away ? ` <span class="muted">vs</span> ${esc(o.away)}` : "");
const effOdds = (o, c) => 1 + (o - 1) * (1 - (c || 0));
const roundStep = (x, step) => (step <= 0.01 ? Math.round(x * 100) / 100 : Math.round(Math.round(x / step) * step * 100) / 100);

async function api(path, opts = {}) {
  const o = { method: opts.method || "GET", headers: {} };
  if (opts.body !== undefined) {
    o.method = opts.method || "POST";
    o.headers["Content-Type"] = "application/json";
    o.body = JSON.stringify(opts.body);
  }
  const r = await fetch(path, o);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || (typeof data.detail === "string" ? data.detail : "") || `Error ${r.status}`);
  return data;
}
let toastTimer;
function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (err ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = "toast"), err ? 6000 : 3000);
}
async function run(fn, btn) {
  if (btn) btn.disabled = true;
  try { return await fn(); } catch (e) { toast(e.message, true); } finally { if (btn) btn.disabled = false; }
}

// ---------- estado ----------
const S = { books: [], status: null, settings: null, opps: [], lastScan: null, ops: [], selOp: null, catalog: null, editing: {}, tab: "inicio" };

// ---------- pestañas ----------
function setTab(tab) {
  S.tab = tab;
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("active", s.id === "tab-" + tab));
  history.replaceState(null, "", "#" + tab);
  if (tab === "ajustes") renderSettings();
  if (tab === "operaciones" || tab === "historial") loadOps();
}
$("#tabs").addEventListener("click", (e) => { const b = e.target.closest("button[data-tab]"); if (b) setTab(b.dataset.tab); });

// ---------- estado general / inicio ----------
async function loadStatus() {
  S.status = await api("/api/status");
  renderStatus();
}
function renderStatus() {
  const st = S.status; if (!st) return;
  const feedDemo = st.feed.feed === "demo";
  const ex = st.exchange;
  $("#pills").innerHTML = [
    st.live ? `<span class="pill live" title="Las apuestas de Betfair son reales"><span class="dot"></span>MODO REAL</span>`
      : `<span class="pill warn" title="${esc(st.sim_reason)}"><span class="dot"></span>SIMULACIÓN</span>`,
    feedDemo ? `<span class="pill"><span class="dot"></span>Datos de ejemplo</span>`
      : `<span class="pill ok"><span class="dot"></span>${esc(st.feed.label)}${st.feed.remaining != null ? " · " + esc(st.feed.remaining) + " peticiones" : ""}</span>`,
    `<span class="pill ${ex.connected ? "ok" : ""}"><span class="dot"></span>${esc(ex.label)}${ex.balance != null ? " · " + eur(ex.balance) : ""}</span>`,
  ].join("");

  const used = st.spent_today, max = st.max_daily, ratio = Math.min(1, used / max);
  $("#kpis").innerHTML = `
    <div class="kpi"><div class="label">Oportunidades ahora</div><div class="value num">${st.opportunities}</div>
      <div class="sub">${st.last_scan.at ? "Última búsqueda " + ago(st.last_scan.at) : "Aún no has buscado"}</div></div>
    <div class="kpi"><div class="label">Operaciones en marcha</div><div class="value num">${st.open_ops + st.exposed_ops.length}</div>
      <div class="sub">${st.exposed_ops.length ? `<span class="neg">${st.exposed_ops.length} con riesgo abierto</span>` : "Ninguna con riesgo abierto"}</div></div>
    <div class="kpi"><div class="label">Apostado hoy</div><div class="value num">${eur(used)}</div>
      <div class="sub">Límite diario ${eur(max)}</div><div class="bar ${ratio > 0.85 ? "hot" : ""}"><span style="width:${ratio * 100}%"></span></div></div>
    <div class="kpi"><div class="label">Beneficio liquidado</div><div class="value">${signed(st.realized_profit)}</div>
      <div class="sub">Total apostado ${eur(st.staked_total)}</div></div>`;

  const nBooks = S.settings ? S.settings.bookmakers.length : 0;
  const items = [
    [feedDemo ? null : true, "Datos de cuotas reales", feedDemo ? "Usando datos de ejemplo (SUREBET_FEED=demo)." : `Leyendo de: ${esc(st.feed.label.replace(/^Webs: /, ""))}.`],
    [st.live ? (ex.connected ? true : (ex.error && ex.error !== "Sin comprobar todavía." ? false : null)) : null, "Betfair conectado",
      st.live ? (ex.connected ? `Saldo disponible ${eur(ex.balance)}.` : esc(ex.error) + ` <button class="btn small" data-action="check-bf">Comprobar Betfair</button>`)
        : `En simulación (${esc(st.sim_reason)}). Saldo virtual ${eur(ex.balance)}.`],
    [st.live || null, "Modo real activado", st.live ? "Las apuestas en Betfair se envían de verdad, siempre tras tu confirmación." : "Añade SUREBET_LIVE=1 en .env y reinicia para apostar de verdad."],
    [nBooks >= 2, "Tus casas elegidas", `${nBooks} casas seleccionadas. <a href="#ajustes" data-goto="ajustes">Cambiar</a>`],
  ];
  $("#checklist").innerHTML = items.map(([ok, t, d], i) =>
    `<li class="${ok === true ? "done" : ok === false ? "bad" : ""}"><span class="mark">${ok === true ? "✓" : ok === false ? "!" : i + 1}</span><div><b>${t}</b><small>${d}</small></div></li>`).join("");

  const alerts = [];
  st.exposed_ops.forEach((id) => alerts.push(`<div class="alert danger"><span><b>Riesgo abierto en la operación #${id}.</b> Hay apuestas hechas sin cubrir todos los resultados.</span><button class="btn small danger" data-action="open-op" data-op="${id}">Resolver</button></div>`));
  st.unknown_ops.forEach((id) => alerts.push(`<div class="alert danger"><span><b>Operación #${id}:</b> no se sabe si Betfair aceptó una apuesta. Revísalo en Betfair.</span><button class="btn small danger" data-action="open-op" data-op="${id}">Ver</button></div>`));
  if (st.last_scan.error) alerts.push(`<div class="alert warn"><span>Última búsqueda: ${esc(st.last_scan.error)}</span></div>`);
  $("#alerts").innerHTML = alerts.join("");

  $("#c-opps").textContent = st.opportunities || "";
  const active = st.open_ops + st.exposed_ops.length;
  $("#c-ops").textContent = active || "";
  $("#c-ops").classList.toggle("bad", st.exposed_ops.length > 0);
}

// ---------- oportunidades ----------
async function loadOpps() {
  const d = await api("/api/opportunities");
  S.opps = d.opportunities; S.lastScan = d.last_scan;
  renderOpps();
}
async function doScan(btn) {
  await run(async () => {
    const d = await api("/api/scan", { body: {} });
    S.opps = d.opportunities; S.lastScan = d.last_scan;
    renderOpps();
    toast(d.opportunities.length ? `${d.opportunities.length} surebets encontradas` : "Sin surebets ahora mismo");
    loadStatus();
  }, btn);
}
// Mismo algoritmo que core.plan_stakes: prueba redondear cada pata arriba/abajo
// y se queda con la combinación que más gana en el peor resultado.
function planFor(opp, budget) {
  const rounding = S.settings ? S.settings.rounding : 0.01;
  const effs = opp.legs.map((l) => effOdds(l.odds, l.commission));
  const inv = effs.reduce((a, e) => a + 1 / e, 0);
  const options = opp.legs.map((l, i) => {
    const x = budget / effs[i] / inv;
    const step = l.mode === "auto" ? 0.01 : (l.step ?? rounding);
    if (step <= 0.01) return [Math.round(x * 100) / 100];
    const lo = Math.round(Math.floor(x / step) * step * 100) / 100;
    return [lo, Math.round((lo + step) * 100) / 100];
  });
  let best = null;
  const walk = (i, acc) => {
    if (i === options.length) {
      if (Math.min(...acc) <= 0) return;
      const total = acc.reduce((a, b) => a + b, 0);
      const min = Math.min(...acc.map((s, k) => s * effs[k] - total));
      const dev = Math.abs(total - budget);
      if (!best || min > best.min + 1e-9 || (Math.abs(min - best.min) < 1e-9 && dev < best.dev)) best = { stakes: [...acc], total, min, dev };
      return;
    }
    for (const v of options[i]) walk(i + 1, [...acc, v]);
  };
  walk(0, []);
  return best || { stakes: options.map((o) => o[0]), total: 0, min: 0 };
}
// Avisos para cuidar las cuentas de las casas normales.
function careWarnings(legs, stakes, margin) {
  const st = S.settings; if (!st) return [];
  const w = [];
  if (margin > st.max_margin_warn) w.push(`Margen muy alto (${pct(margin)}): puede ser un error de cuota; las casas suelen anularlas y marcar la cuenta.`);
  legs.forEach((l, i) => {
    if (l.mode !== "auto" && stakes[i] > st.max_manual_stake) w.push(`${l.bookmaker}: ${eur(stakes[i])} supera tu máximo recomendado (${eur(st.max_manual_stake)}). Baja el presupuesto.`);
    const b = S.books.find((x) => x.bookmaker === l.bookmaker);
    if (b && b.warn) w.push(`Ya llevas ${eur(b.profit)} ganados en ${l.bookmaker}: mejor reparte en otras casas.`);
  });
  return [...new Set(w)];
}
const careHtml = (w) => w.map((t) => `<div class="warnline">⚠ ${esc(t)}</div>`).join("");

function oppCard(o) {
  const budget = S.settings ? S.settings.budget : o.budget;
  const p = planFor(o, budget);
  const sport = SPORTS_ES[o.sport] || o.sport;
  return `<article class="card opp" data-opp="${esc(o.id)}">
    <div class="meta"><span>${esc(sport)} · ${esc(o.league)}</span><span>${esc(fdate(o.date))}</span></div>
    <div><span class="chip market">${esc(o.market_label || "Ganador del partido")}</span></div>
    <div style="display:flex;justify-content:space-between;gap:10px;align-items:center">
      <h3>${esc(o.home)} <span class="muted">vs</span> ${esc(o.away)}</h3>
      <span class="badge big" title="Margen teórico tras comisiones">+${pct(o.margin)}</span>
    </div>
    <table class="legs"><thead><tr><th>Resultado</th><th>Casa</th><th class="r">Cuota</th><th class="r">Apuesta</th></tr></thead><tbody>
      ${o.legs.map((l, i) => `<tr><td>${esc(l.label)}</td>
        <td>${l.url ? `<a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.bookmaker)}</a>` : esc(l.bookmaker)}
          <span class="chip ${l.mode}">${l.mode === "auto" ? "AUTO" : "MANUAL"}</span>${l.commission ? ` <span class="muted">(${pct(l.commission)} com.)</span>` : ""}</td>
        <td class="r num"><b>${nf2.format(l.odds)}</b></td><td class="r num" data-stake="${i}">${eur(p.stakes[i])}</td></tr>`).join("")}
    </tbody></table>
    <div data-care>${careHtml(careWarnings(o.legs, p.stakes, o.margin))}</div>
    <footer>
      <label class="budget">Presupuesto <input type="number" min="1" step="1" value="${budget}" data-budget> €</label>
      <span>Ganas mínimo <b data-minprofit>${signed(p.min)}</b></span>
      <button class="btn primary" data-action="operate">Operar</button>
    </footer>
  </article>`;
}
// Orden y filtros de la lista (se recuerdan en este navegador).
const VIEW = (() => { try { return JSON.parse(localStorage.getItem("oppView")) || {}; } catch { return {}; } })();
function saveView() { try { localStorage.setItem("oppView", JSON.stringify(VIEW)); } catch {} }
function visibleOpps() {
  const minPct = VIEW.min || 0, market = VIEW.market || "", sort = VIEW.sort || "margin";
  const budget = S.settings ? S.settings.budget : 50;
  const sport = VIEW.sport || "";
  const list = S.opps.filter((o) => o.margin * 100 >= minPct && (!market || (o.group || "Ganador") === market)
    && (!sport || o.sport === sport));
  const key = {
    margin: (o) => -o.margin,
    profit: (o) => -planFor(o, budget).min,
    date: (o) => new Date(o.date).getTime() || 0,
  }[sort];
  return list.map((o) => [key(o), o]).sort((a, b) => a[0] - b[0]).map((x) => x[1]);
}
function fillFilter(sel, values, labelFn, current) {
  const opts = [...new Set(values)].sort((a, b) => labelFn(a).localeCompare(labelFn(b)));
  if (current && !opts.includes(current)) opts.unshift(current);
  sel.innerHTML = `<option value="">Todos</option>` + opts.map((v) => `<option value="${esc(v)}" ${v === current ? "selected" : ""}>${esc(labelFn(v))}</option>`).join("");
}
function renderOpps() {
  const ls = S.lastScan || {};
  fillFilter($("#opp-market"), S.opps.map((o) => o.group || "Ganador"), (g) => g, VIEW.market || "");
  fillFilter($("#opp-sport"), S.opps.map((o) => o.sport), (sp) => SPORTS_ES[sp] || sp, VIEW.sport || "");
  const list = visibleOpps();
  const hidden = S.opps.length - list.length;
  $("#scan-info").textContent = (ls.at ? `Última búsqueda ${ago(ls.at)} · ${ls.events} eventos analizados` : "") +
    (hidden > 0 ? ` · ${hidden} ocultas por los filtros` : "");
  $("#opps").innerHTML = list.length ? list.map(oppCard).join("")
    : `<div class="empty card" style="grid-column:1/-1"><b>${ls.at ? "No hay surebets ahora mismo" : "Pulsa «Buscar ahora»"}</b>
       ${ls.at ? "Es normal: aparecen y desaparecen en minutos. Activa la búsqueda automática o añade más casas en Ajustes." : "Se compararán las cuotas de tus casas elegidas."}</div>`;
}
$("#opps").addEventListener("input", (e) => {
  if (!e.target.matches("[data-budget]")) return;
  const card = e.target.closest("[data-opp]");
  const o = S.opps.find((x) => x.id === card.dataset.opp);
  const b = parseFloat(e.target.value);
  if (!o || !(b > 0)) return;
  const p = planFor(o, b);
  card.querySelectorAll("[data-stake]").forEach((td) => (td.textContent = eur(p.stakes[+td.dataset.stake])));
  card.querySelector("[data-minprofit]").innerHTML = signed(p.min);
  card.querySelector("[data-care]").innerHTML = careHtml(careWarnings(o.legs, p.stakes, o.margin));
});
$("#btn-scan").addEventListener("click", (e) => doScan(e.currentTarget));
$("#opp-sort").value = VIEW.sort || "margin";
$("#opp-min").value = VIEW.min || 0;
["#opp-sort", "#opp-min", "#opp-market", "#opp-sport"].forEach((id) => $(id).addEventListener("change", () => {
  VIEW.sort = $("#opp-sort").value; VIEW.min = parseFloat($("#opp-min").value) || 0;
  VIEW.market = $("#opp-market").value; VIEW.sport = $("#opp-sport").value;
  saveView(); renderOpps();
}));
let autoTimer = null;
$("#auto-scan").addEventListener("change", (e) => {
  clearInterval(autoTimer);
  if (e.target.checked) { doScan(); autoTimer = setInterval(() => doScan(), 60000); }
});

// ---------- operaciones ----------
async function loadOps() {
  S.ops = await api("/api/operations");
  renderOps(); renderHistory();
  loadBooks().catch(() => {});
}
function opById(id) { return S.ops.find((o) => o.id === id); }
function renderOps() {
  const active = S.ops.filter((o) => !["liquidada", "cancelada"].includes(o.state));
  $("#op-list").innerHTML = active.length ? active.map((o) => `
    <div class="card oprow ${S.selOp === o.id ? "sel" : ""}" data-action="open-op" data-op="${o.id}">
      <div><b>#${o.id} · ${evName(o)}</b><div class="muted">${[fdate(o.date), o.league, o.source].filter(Boolean).map(esc).join(" · ")}</div></div>
      <div class="actions"><span class="muted">Apostado ${eur(o.staked)}</span><span class="badge ${STATE_BADGE[o.state]}">${esc(o.state)}</span></div>
    </div>`).join("")
    : (S.selOp ? "" : `<div class="empty card"><b>No hay operaciones en marcha</b>Ve a Oportunidades y pulsa «Operar» en una surebet.</div>`);
  const op = S.selOp && opById(S.selOp);
  $("#op-detail").innerHTML = op ? opDetail(op) : "";
}
function plTable(op, key, title, hint) {
  return `<div class="card"><h2>${title}</h2><p class="muted" style="margin-top:-6px">${hint}</p>
    <table class="legs"><tbody>${op.legs.map((l) => `<tr><td>Si gana ${esc(l.label)}</td><td class="r">${signed(op[key][l.outcome])}</td></tr>`).join("")}</tbody></table></div>`;
}
function manualForm(op, l, odds, stake, label = "Hecha") {
  return `<div class="row">
    <label class="field">Cuota conseguida<input type="number" step="0.01" min="1.01" value="${odds ?? ""}" data-f="odds"></label>
    <label class="field">Importe apostado (€)<input type="number" step="0.01" min="0.01" value="${stake ?? ""}" data-f="stake"></label>
    <label class="field">Casa<input type="text" value="${esc(l.bookmaker)}" data-f="bookmaker" style="width:150px"></label>
    <button class="btn primary" data-action="manual" data-op="${op.id}" data-leg="${l.id}">${label}</button>
  </div>`;
}
function stepBody(op, l) {
  const manualPending = op.legs.some((x) => x.mode === "manual" && x.status === "pending");
  const closed = ["liquidada", "cancelada"].includes(op.state);
  const chip = `<span class="chip ${l.mode}">${l.mode === "auto" ? "AUTO" : "MANUAL"}</span>`;
  const head = `<h4>${esc(l.label)} en ${esc(l.bookmaker)} ${chip}</h4>`;
  const editing = S.editing[`${op.id}:${l.id}`];
  const note = l.note && l.status !== "placed" ? `<div class="muted">${esc(l.note)}</div>` : "";
  if (l.status === "placed") {
    return head + `<div>✓ <b>${eur(l.stake)}</b> a cuota <b>${nf2.format(l.odds)}</b>
      ${l.simulated ? `<span class="badge amber">simulada</span>` : ""}${l.ref ? ` <span class="muted">ref ${esc(l.ref)}</span>` : ""}</div>` +
      (editing ? manualForm(op, l, l.odds, l.stake, "Guardar") : closed ? "" : `<div><button class="btn ghost small" data-action="edit" data-key="${op.id}:${l.id}">Corregir</button></div>`);
  }
  if (closed) return head + `<div class="muted">No realizada.</div>`;
  if (l.status === "skipped") {
    return head + `<div class="muted">Marcada como no realizada.</div>` +
      (editing ? manualForm(op, l, l.planned_odds, null) : `<div class="actions"><button class="btn small" data-action="reopen" data-op="${op.id}" data-leg="${l.id}">Reabrir</button>
       <button class="btn ghost small" data-action="edit" data-key="${op.id}:${l.id}">La hice igualmente: anotar</button></div>`);
  }
  if (l.status === "unknown") {
    return head + `<div class="neg">No se sabe si Betfair aceptó esta apuesta. Mira «Mis apuestas» en Betfair antes de hacer nada.</div>${note}` +
      (editing ? manualForm(op, l, l.planned_odds, null) : `<div class="actions"><button class="btn small" data-action="edit" data-key="${op.id}:${l.id}">Sí se hizo: anotar</button>
       <button class="btn small" data-action="reopen" data-op="${op.id}" data-leg="${l.id}">No se hizo: reabrir</button></div>`);
  }
  if (l.mode === "manual") {
    return head + `<div>Apuesta <b>${eur(l.suggested_stake)}</b> a <b>${esc(l.label)}</b> con cuota <b>${nf2.format(l.planned_odds)}</b> o mejor.
      ${l.url ? `<a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">Abrir ${esc(l.bookmaker)} ↗</a>` : ""}</div>
      <div class="muted">Si la cuota ha bajado, anota la real: los importes pendientes se recalculan. Si ya no compensa, pulsa «No pude».</div>
      ${careHtml(careWarnings([l], [l.suggested_stake], 0))}
      ${manualForm(op, l, l.planned_odds, l.suggested_stake)}
      <div><button class="btn ghost small" data-action="skip" data-op="${op.id}" data-leg="${l.id}">No pude hacerla</button>
      ${l.bookmaker === S.settings?.auto_bookmaker && l.can_auto !== false ? `<button class="btn ghost small" data-action="mode" data-mode="auto" data-op="${op.id}" data-leg="${l.id}">Hacerla automática</button>` : ""}</div>`;
  }
  // automática pendiente
  const toManual = `<button class="btn ghost small" data-action="mode" data-mode="manual" data-op="${op.id}" data-leg="${l.id}">Hacerla manual</button>`;
  if (manualPending) {
    return head + `<div class="muted">Va la última: cuando anotes las apuestas manuales, se calcula el importe exacto con las cuotas reales que conseguiste.</div>${note}<div>${toManual}</div>`;
  }
  const p = l.prepared;
  const fresh = p && (Date.now() / 1000 - p.at) < 60;
  if (!fresh) {
    return head + `<div>Importe aproximado <b>${eur(l.suggested_stake)}</b> a cuota ${nf2.format(l.planned_odds)}.</div>${note}
      <div class="actions"><button class="btn primary" data-action="prepare" data-op="${op.id}" data-leg="${l.id}">Consultar Betfair</button>${toManual}</div>`;
  }
  const minPl = Math.min(...Object.values(p.projection));
  const needAccept = p.worse || minPl < 0;
  const live = S.status && S.status.live;
  return head + `<div class="prep">
      <dl>
        <dt>Partido en Betfair</dt><dd>${esc(p.event_name)} <span class="muted">(${esc(p.market_name)})</span></dd>
        <dt>Selección</dt><dd>${esc(p.runner_name)}</dd>
        <dt>Cuota ahora</dt><dd>${nf2.format(p.price)} ${p.worse ? `<span class="badge red">peor que ${nf2.format(l.planned_odds)}</span>` : `<span class="badge">ok</span>`}</dd>
        <dt>Disponible</dt><dd>${eur(p.size_available)}</dd>
        <dt>Importe a apostar</dt><dd>${eur(p.stake)}</dd>
        <dt>Resultado final</dt><dd>${op.legs.map((x) => `${esc(x.label)}: ${signed(p.projection[x.outcome])}`).join(" · ")}</dd>
      </dl>
      <div class="muted">Comprueba que el partido y la selección son los correctos. Caduca en <b data-expire="${p.at + 60}">60</b> s.</div>
      <div class="row">
        <label class="field">Escribe SI para confirmar<input type="text" data-f="confirm" style="width:120px" autocomplete="off"></label>
        ${needAccept ? `<label class="switch"><input type="checkbox" data-f="accept"> Acepto ${minPl < 0 ? "una posible pérdida para cubrir el riesgo" : "la cuota peor"}</label>` : ""}
        <button class="btn ${live ? "danger" : "primary"}" data-action="place" data-op="${op.id}" data-leg="${l.id}">${live ? "Apostar en Betfair (REAL)" : "Simular apuesta"}</button>
        <button class="btn ghost small" data-action="prepare" data-op="${op.id}" data-leg="${l.id}">Actualizar</button>
      </div>
    </div>`;
}
function opDetail(op) {
  const ordered = [...op.legs].sort((a, b) => (a.mode === "auto") - (b.mode === "auto"));
  const closed = ["liquidada", "cancelada"].includes(op.state);
  const settled = op.settled;
  return `<div class="detail">
    <div class="card">
      <div class="detail-head">
        <div><div class="muted">${[`Operación #${op.id}`, op.source && `desde ${op.source}`, op.market_label, op.league, fdate(op.date)].filter(Boolean).map(esc).join(" · ")}</div>
          <h2>${evName(op)}</h2></div>
        <div class="actions"><span class="badge big ${STATE_BADGE[op.state]}">${esc(op.state)}</span><span class="badge big">+${pct(op.margin)}</span>
          <button class="btn ghost small" data-action="close-op">Cerrar</button></div>
      </div>
      ${op.next_step ? `<div class="next" style="margin-top:14px">➜ ${esc(op.next_step)}</div>` : ""}
      ${settled ? `<div class="next" style="margin-top:14px">Liquidada: ${settled.winner === "void" ? "anulada" : "ganó " + esc(op.legs.find((l) => l.outcome === settled.winner)?.label)} · beneficio ${signed(settled.profit)}</div>` : ""}
    </div>
    <div class="card"><h2>Pasos</h2><div class="steps">
      ${ordered.map((l, i) => `<div class="step ${l.status}"><span class="n">${l.status === "placed" ? "✓" : l.status === "unknown" ? "?" : i + 1}</span><div class="body">${stepBody(op, l)}</div></div>`).join("")}
    </div></div>
    <div class="pl">
      ${plTable(op, "projection", "Si completas el plan", "Beneficio por resultado con lo apostado más lo pendiente.")}
      ${plTable(op, "current", "Ahora mismo", "Solo con las apuestas ya hechas (riesgo real actual).")}
    </div>
    ${closed ? "" : `<div class="card"><h2>Cerrar operación</h2><div class="actions">
      ${op.staked > 0 ? `<label class="field">Resultado del evento<select data-f="winner">${op.legs.map((l) => `<option value="${l.outcome}">${esc(l.label)}</option>`).join("")}<option value="void">Anulado / devuelto</option></select></label>
        <button class="btn primary" data-action="settle" data-op="${op.id}">Liquidar</button>`
        : `<button class="btn" data-action="cancel" data-op="${op.id}">Cancelar operación</button><span class="muted">Aún no hay apuestas hechas.</span>`}
    </div></div>`}
    <div class="card"><h2>Registro</h2><ol class="log">${op.log.slice().reverse().map((e) => `<li><span class="num">${esc(new Date(e.at).toLocaleTimeString("es-ES"))}</span> · ${esc(e.msg)}</li>`).join("")}</ol></div>
  </div>`;
}
function replaceOp(op) {
  const i = S.ops.findIndex((o) => o.id === op.id);
  if (i >= 0) S.ops[i] = op; else S.ops.unshift(op);
  renderOps(); renderHistory(); loadStatus(); loadBooks().catch(() => {});
}
function openOp(id) {
  S.selOp = id;
  setTab("operaciones");
  setTimeout(() => $("#op-detail").scrollIntoView({ behavior: "smooth", block: "start" }), 120);
}

// ---------- historial ----------
async function loadBooks() {
  S.books = await api("/api/bookmakers/stats");
  renderBooks();
}
function renderBooks() {
  const t = $("#books"); if (!t) return;
  t.innerHTML = `<thead><tr><th>Casa</th><th class="r">Apuestas</th><th class="r">Volumen</th><th class="r">Pendiente</th><th class="r">Beneficio</th><th>Última</th><th></th></tr></thead><tbody>
    ${S.books.length ? S.books.map((b) => `<tr><td><b>${esc(b.bookmaker)}</b>${b.exchange ? ' <span class="chip auto">EXCHANGE</span>' : ""}</td>
      <td class="r num">${b.bets}</td><td class="r num">${eur(b.staked)}</td><td class="r num">${eur(b.open_stake)}</td>
      <td class="r">${signed(b.profit)}</td><td>${esc(fdate(b.last_at))}</td>
      <td>${b.warn ? '<span class="badge amber">reparte</span>' : ""}</td></tr>`).join("")
      : `<tr><td colspan="7" class="empty">Aún no hay apuestas.</td></tr>`}</tbody>`;
}
function renderHistory() {
  $("#hist").innerHTML = `<thead><tr><th>#</th><th>Creada</th><th>Evento</th><th>Estado</th><th class="r">Apostado</th><th class="r">Beneficio</th></tr></thead><tbody>
    ${S.ops.length ? S.ops.map((o) => {
      const profit = o.settled ? signed(o.settled.profit) : o.state === "cancelada" ? "—" : `<span class="muted">previsto</span> ${signed(Math.min(...Object.values(o.projection)))}`;
      return `<tr class="click" data-action="open-op" data-op="${o.id}"><td>${o.id}</td><td>${esc(fdate(o.created_at))}</td>
        <td>${evName(o)}<div class="muted">${[o.source, o.league].filter(Boolean).map(esc).join(" · ")}</div></td>
        <td><span class="badge ${STATE_BADGE[o.state]}">${esc(o.state)}</span></td><td class="r num">${eur(o.staked)}</td><td class="r">${profit}</td></tr>`;
    }).join("") : `<tr><td colspan="6" class="empty">Todavía no hay operaciones.</td></tr>`}</tbody>`;
}

// ---------- ajustes ----------
async function loadSettings() { S.settings = await api("/api/settings"); }
async function loadCatalog() {
  try { S.catalog = await api("/api/catalog"); } catch (e) { S.catalog = { sports: [], bookmakers: [] }; }
}
function renderSettings() {
  const st = S.settings; if (!st) return;
  const cat = S.catalog || { sports: [], bookmakers: [] };
  const allBooks = [...new Set([...st.bookmakers, ...cat.bookmakers])];
  const isEs = (b) => / ES$/.test(b) || /betfair/i.test(b);
  allBooks.sort((a, b) => (isEs(b) - isEs(a)) || a.localeCompare(b));
  const sports = cat.sports.length ? cat.sports : st.sports.filter((s) => s !== "*").map((s) => ({ slug: s, name: s }));
  const allSports = st.sports.includes("*");
  const allMarkets = (st.markets || ["*"]).includes("*");
  const f = $("#settings");
  f.innerHTML = `
    <fieldset><legend>Casas en las que tienes cuenta (${st.bookmakers.length})</legend>
      <p class="muted" style="margin-top:0">Marca solo casas donde puedas apostar. Las españolas (ES) salen primero. Máximo 30. Solo se leen las casas que tienen lector (ver Guía).</p>
      <input type="search" placeholder="Filtrar casas…" id="book-filter" style="margin-bottom:10px;width:min(320px,100%)">
      <div class="checks" id="book-checks">${allBooks.map((b) => `<label data-name="${esc(b.toLowerCase())}"><input type="checkbox" name="bk" value="${esc(b)}" ${st.bookmakers.includes(b) ? "checked" : ""}> ${esc(b)}${isEs(b) ? "" : ' <span class="muted">(int.)</span>'}</label>`).join("")}</div>
    </fieldset>
    <fieldset><legend>Apuesta automática y comisiones</legend>
      <div class="fields">
        <label>Casa automática (exchange con API)<select name="auto_bookmaker">${allBooks.map((b) => `<option ${b === st.auto_bookmaker ? "selected" : ""}>${esc(b)}</option>`).join("")}</select></label>
      </div>
      <p class="muted">Comisión sobre ganancias de los exchanges (en %). Betfair Exchange suele cobrar alrededor del 5 %. Las casas normales no cobran comisión.</p>
      <div class="fields" id="comm-fields"></div>
    </fieldset>
    <fieldset><legend>Deportes</legend>
      <label class="switch" style="margin-bottom:10px"><input type="checkbox" name="sport_all" ${allSports ? "checked" : ""}> <b>Todos los deportes</b></label>
      <div class="checks" id="sport-checks" ${allSports ? 'style="opacity:.45;pointer-events:none"' : ""}>${sports.map((s) => `<label><input type="checkbox" name="sport" value="${esc(s.slug)}" ${allSports || st.sports.includes(s.slug) ? "checked" : ""}> ${esc(SPORTS_ES[s.slug] || s.name)}</label>`).join("")}</div>
    </fieldset>
    <fieldset><legend>Mercados</legend>
      <div class="checks" style="max-height:none;grid-template-columns:1fr">
        <label><input type="radio" name="market_scope" value="all" ${allMarkets ? "checked" : ""}> <span><b>Todos los mercados y líneas</b> (ganador, más/menos, hándicaps, ambos marcan, córners, tarjetas, jugadores, periodos, sets, mapas…)</span></label>
        <label><input type="radio" name="market_scope" value="main" ${allMarkets ? "" : "checked"}> <span>Solo principales (ganador, más/menos y hándicap del partido)</span></label>
      </div>
      <p class="muted">Solo se comparan resultados que cubren todas las posibilidades (más/menos, sí/no, 1X2, par/impar, doble oportunidad contra 1X2…). Mercados como resultado exacto o goleador no se usan porque no garantizan cubrirlo todo. Betfair solo apuesta automático en el ganador del partido; el resto es manual.</p>
    </fieldset>
    <fieldset><legend>Búsqueda</legend><div class="fields">
      <label>Horas hacia delante<input type="number" name="hours_ahead" min="1" max="336" value="${st.hours_ahead}"></label>
      <label>Máx. eventos por búsqueda<input type="number" name="max_events" min="1" max="500" value="${st.max_events}"></label>
      <label>Ignorar cuotas con más de (s)<input type="number" name="max_odds_age_s" min="10" value="${st.max_odds_age_s}"></label>
      <label>Margen mínimo (%)<input type="number" name="min_margin_pct" step="0.1" min="0" value="${+(st.min_margin * 100).toFixed(2)}"></label>
    </div></fieldset>
    <fieldset><legend>Dinero y límites</legend><div class="fields">
      <label>Presupuesto por defecto (€)<input type="number" name="budget" min="1" step="1" value="${st.budget}"></label>
      <label>Máximo por operación (€)<input type="number" name="max_budget_op" min="1" step="1" value="${st.max_budget_op}"></label>
      <label>Máximo diario (€)<input type="number" name="max_daily" min="1" step="1" value="${st.max_daily}"></label>
      <label>Redondear apuestas manuales a<select name="rounding">${[[0.01, "céntimos"], [0.5, "0,50 €"], [1, "1 €"], [5, "5 €"], [10, "10 €"]].map(([v, t]) => `<option value="${v}" ${+st.rounding === v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    </div><p class="muted">Redondear a cifras redondas hace las apuestas menos llamativas para las casas.</p></fieldset>
    <fieldset><legend>Cuidar tus cuentas</legend><div class="fields">
      <label>Apuesta manual máxima recomendada (€)<input type="number" name="max_manual_stake" min="1" step="1" value="${st.max_manual_stake}"></label>
      <label>Avisar de posible error de cuota si margen &gt; (%)<input type="number" name="max_margin_warn_pct" min="0.5" step="0.5" value="${+(st.max_margin_warn * 100).toFixed(2)}"></label>
      <label>Avisar cuando lleves ganado en una casa (€)<input type="number" name="book_profit_warn" min="1" step="1" value="${st.book_profit_warn}"></label>
    </div><p class="muted">Solo son avisos: la web te señala cuándo una apuesta o una casa puede llamar la atención.</p></fieldset>
    <div class="savebar"><button class="btn primary" type="submit">Guardar ajustes</button></div>`;
  renderCommissions();
}
function renderCommissions() {
  const st = S.settings;
  const sel = [...document.querySelectorAll('#settings input[name="bk"]:checked')].map((i) => i.value);
  const prev = {};
  document.querySelectorAll("#comm-fields input").forEach((i) => (prev[i.dataset.bk] = i.value));
  const isExchange = (b) => /exchange|betfair|matchbook|smarkets|betdaq/i.test(b) || (st.commissions[b] || 0) > 0 || b === st.auto_bookmaker;
  $("#comm-fields").innerHTML = sel.filter(isExchange).map((b) => {
    const v = prev[b] ?? +(((st.commissions[b] || 0) * 100).toFixed(2));
    return `<label>${esc(b)}<input type="number" step="0.1" min="0" max="49" data-bk="${esc(b)}" value="${v}"></label>`;
  }).join("");
}
$("#settings").addEventListener("change", (e) => {
  if (e.target.name === "bk") renderCommissions();
  if (e.target.name === "sport_all") {
    const box = $("#sport-checks");
    box.style.opacity = e.target.checked ? ".45" : ""; box.style.pointerEvents = e.target.checked ? "none" : "";
  }
});
$("#settings").addEventListener("input", (e) => {
  if (e.target.id !== "book-filter") return;
  const q = e.target.value.toLowerCase();
  document.querySelectorAll("#book-checks label").forEach((l) => (l.style.display = l.dataset.name.includes(q) ? "" : "none"));
});
$("#settings").addEventListener("submit", (e) => {
  e.preventDefault();
  const f = e.target;
  const commissions = {};
  document.querySelectorAll("#comm-fields input").forEach((i) => { const v = parseFloat(i.value) || 0; if (v) commissions[i.dataset.bk] = v / 100; });
  const body = {
    bookmakers: [...f.querySelectorAll('input[name="bk"]:checked')].map((i) => i.value),
    sports: f.sport_all.checked ? ["*"] : [...f.querySelectorAll('input[name="sport"]:checked')].map((i) => i.value),
    markets: f.querySelector('input[name="market_scope"]:checked').value === "all" ? ["*"] : ["ML", "Totals", "Spread"],
    auto_bookmaker: f.auto_bookmaker.value, commissions,
    hours_ahead: f.hours_ahead.value, max_events: f.max_events.value, max_odds_age_s: f.max_odds_age_s.value,
    min_margin: (parseFloat(f.min_margin_pct.value) || 0) / 100,
    budget: f.budget.value, max_budget_op: f.max_budget_op.value, max_daily: f.max_daily.value, rounding: f.rounding.value,
    max_manual_stake: f.max_manual_stake.value, book_profit_warn: f.book_profit_warn.value,
    max_margin_warn: (parseFloat(f.max_margin_warn_pct.value) || 5) / 100,
  };
  run(async () => {
    S.settings = await api("/api/settings", { method: "PUT", body });
    toast("Ajustes guardados");
    renderSettings(); renderStatus(); renderOpps();
  }, f.querySelector('[type="submit"]'));
});

// ---------- surebet externa (BetOven u otro escáner) ----------
const KINDS = [["home", "Local (1)"], ["draw", "Empate (X)"], ["away", "Visitante (2)"], ["other", "Otro mercado"]];
function extLegRow(i, kind) {
  return `<div class="extleg" data-leg-row>
    <span class="n">${i + 1}</span>
    <label class="field">Selección<input data-x="label" maxlength="80" placeholder="p. ej. Más de 2.5 goles"></label>
    <label class="field">Tipo<select data-x="kind">${KINDS.map(([v, t]) => `<option value="${v}" ${v === kind ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    <label class="field">Casa<input data-x="bookmaker" list="books-list" maxlength="60" placeholder="Codere ES"></label>
    <label class="field">Cuota<input data-x="odds" type="number" step="0.01" min="1.01"></label>
    <span class="stake" data-x-stake>—</span>
    <button type="button" class="btn ghost small" data-x-del title="Quitar" aria-label="Quitar apuesta">✕</button>
  </div>`;
}
function extReset() {
  const f = $("#ext-form");
  f.reset();
  f.budget.value = S.settings ? S.settings.budget : 50;
  $("#ext-legs").innerHTML = extLegRow(0, "other") + extLegRow(1, "other");
  $("#books-list").innerHTML = (S.catalog?.bookmakers?.length ? S.catalog.bookmakers : S.settings?.bookmakers || []).map((b) => `<option value="${esc(b)}">`).join("");
  extPreview();
}
function extRows() {
  return [...document.querySelectorAll("#ext-legs [data-leg-row]")].map((r) => ({
    row: r, label: r.querySelector('[data-x="label"]').value.trim(), kind: r.querySelector('[data-x="kind"]').value,
    bookmaker: r.querySelector('[data-x="bookmaker"]').value.trim(), odds: parseFloat(r.querySelector('[data-x="odds"]').value),
  }));
}
function extPreview() {
  const rows = extRows();
  rows.forEach((r, i) => (r.row.querySelector(".n").textContent = i + 1));
  const budget = parseFloat($("#ext-form").budget.value);
  const ok = rows.length >= 2 && rows.every((r) => r.odds > 1) && budget > 0;
  const out = $("#ext-preview");
  rows.forEach((r) => (r.row.querySelector("[data-x-stake]").textContent = "—"));
  if (!ok) { out.textContent = "Rellena las cuotas para ver el reparto."; return; }
  const auto = S.settings?.auto_bookmaker;
  const legs = rows.map((r) => ({ odds: r.odds, commission: S.settings?.commissions?.[r.bookmaker] || 0, mode: r.bookmaker === auto && r.kind !== "other" ? "auto" : "manual" }));
  const inv = legs.reduce((a, l) => a + 1 / effOdds(l.odds, l.commission), 0);
  if (inv >= 1) { out.innerHTML = `<span class="neg">No es surebet: margen ${pct(1 / inv - 1)}</span>`; return; }
  const p = planFor({ legs }, budget);
  rows.forEach((r, i) => (r.row.querySelector("[data-x-stake]").textContent = eur(p.stakes[i])));
  out.innerHTML = `Margen <b class="pos">+${pct(1 / inv - 1)}</b> · ganas mínimo ${signed(p.min)}`;
}
$("#ext").addEventListener("toggle", (e) => { if (e.target.open && !$("#ext-legs").children.length) extReset(); });
$("#ext-form").addEventListener("input", extPreview);
$("#ext-form").addEventListener("change", extPreview);
$("#ext-add").addEventListener("click", () => {
  const n = extRows().length;
  if (n >= 4) return toast("Máximo 4 apuestas", true);
  $("#ext-legs").insertAdjacentHTML("beforeend", extLegRow(n, "other"));
  extPreview();
});
$("#ext-legs").addEventListener("click", (e) => {
  if (!e.target.closest("[data-x-del]")) return;
  if (extRows().length <= 2) return toast("Una surebet necesita al menos 2 apuestas", true);
  e.target.closest("[data-leg-row]").remove();
  extPreview();
});
$("#ext-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const f = e.target;
  const body = {
    source: f.source.value, home: f.home.value, away: f.away.value, sport: f.sport.value,
    date: f.date.value ? new Date(f.date.value).toISOString() : "", budget: parseFloat(f.budget.value),
    legs: extRows().map(({ label, kind, bookmaker, odds }) => ({ label, kind, bookmaker, odds })),
  };
  run(async () => {
    const op = await api("/api/operations/external", { body });
    $("#ext").open = false; extReset();
    replaceOp(op); openOp(op.id); toast(`Operación #${op.id} creada desde ${op.source}`);
  }, f.querySelector('[type="submit"]'));
});

// ---------- acciones (delegación) ----------
document.addEventListener("click", (e) => {
  const goto = e.target.closest("[data-goto]");
  if (goto) { e.preventDefault(); setTab(goto.dataset.goto); if (goto.dataset.scan) doScan($("#btn-scan")); return; }
  const el = e.target.closest("[data-action]");
  if (!el) return;
  const a = el.dataset.action, opId = +el.dataset.op, leg = el.dataset.leg;
  const body = el.closest(".body") || el.closest(".card") || document;
  const val = (k) => body.querySelector(`[data-f="${k}"]`);
  const legUrl = `/api/operations/${opId}/legs/${leg}`;
  const done = (op) => { if (op) { S.editing = {}; replaceOp(op); } };
  switch (a) {
    case "open-op": openOp(opId); break;
    case "close-op": S.selOp = null; renderOps(); break;
    case "check-bf": run(async () => { await api("/api/exchange/check", { body: {} }); await loadStatus(); }, el); break;
    case "operate": {
      const card = el.closest("[data-opp]");
      const budget = parseFloat(card.querySelector("[data-budget]").value);
      run(async () => {
        const op = await api("/api/operations", { body: { opportunity_id: card.dataset.opp, budget } });
        replaceOp(op); openOp(op.id); toast(`Operación #${op.id} creada`);
      }, el);
      break;
    }
    case "edit": S.editing[el.dataset.key] = true; renderOps(); break;
    case "manual":
      run(async () => done(await api(legUrl + "/manual", { body: { odds: parseFloat(val("odds").value), stake: parseFloat(val("stake").value), bookmaker: val("bookmaker").value } })), el);
      break;
    case "skip":
      if (confirm("¿Marcar esta apuesta como no realizada? Si ya hiciste otras, quedará riesgo abierto.")) run(async () => done(await api(legUrl + "/skip", { body: {} })), el);
      break;
    case "reopen": run(async () => done(await api(legUrl + "/reopen", { body: {} })), el); break;
    case "mode": run(async () => done(await api(legUrl + "/mode", { body: { mode: el.dataset.mode } })), el); break;
    case "prepare": run(async () => done(await api(legUrl + "/prepare", { body: {} })), el); break;
    case "place": {
      const accept = val("accept");
      run(async () => {
        const op = await api(legUrl + "/place", { body: { confirm: val("confirm").value, accept_worse: accept ? accept.checked : false } });
        done(op);
        const l = op.legs.find((x) => x.id === +leg);
        toast(l.status === "placed" ? "Apuesta hecha" : l.status === "unknown" ? "Estado desconocido: revisa Betfair" : l.note, l.status !== "placed");
      }, el);
      break;
    }
    case "cancel":
      if (confirm("¿Cancelar la operación?")) run(async () => done(await api(`/api/operations/${opId}/cancel`, { body: {} })), el);
      break;
    case "settle":
      run(async () => done(await api(`/api/operations/${opId}/settle`, { body: { winner: val("winner").value } })), el);
      break;
  }
});

// cuenta atrás de la apuesta preparada
setInterval(() => {
  document.querySelectorAll("[data-expire]").forEach((b) => {
    const s = Math.max(0, Math.round(+b.dataset.expire - Date.now() / 1000));
    b.textContent = s;
    if (s === 0) renderOps();
  });
}, 1000);

// ---------- arranque ----------
(async function init() {
  await run(async () => {
    await loadSettings();
    await Promise.all([loadStatus(), loadOpps(), loadOps(), loadCatalog()]);
    await loadBooks(); renderOpps();
  });
  const tab = location.hash.slice(1);
  if (document.getElementById("tab-" + tab)) setTab(tab);
  setInterval(() => loadStatus().catch(() => {}), 20000);
})();
