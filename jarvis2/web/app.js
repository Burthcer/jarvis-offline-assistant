"use strict";
const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;
const pad = (n) => String(n).padStart(2, "0");
const clock = (s) => (s >= 3600 ? `${Math.floor(s / 3600)}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}` : `${pad(Math.floor(s / 60))}:${pad(s % 60)}`);
const WORDS = { idle: ["At your service", 'Say "Jarvis" any time'], listening: ["Listening", "Go ahead, sir"], thinking: ["Thinking", ""], speaking: ["Speaking", ""] };
let history = [], snap = {}, cards = new Map();

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;   // always textContent: whatever was said is shown, never run
  return e;
}
const NS = "http://www.w3.org/2000/svg";
function ring(size, r, width, color) {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
  svg.setAttribute("aria-hidden", "true");
  const c = (stroke) => { const o = document.createElementNS(NS, "circle"); for (const [k, v] of Object.entries({ cx: size / 2, cy: size / 2, r, fill: "none", stroke, "stroke-width": width })) o.setAttribute(k, v); return o; };
  const back = c("#1C232D"), front = c(color), len = 2 * Math.PI * r;
  front.setAttribute("stroke-linecap", "round");
  front.setAttribute("stroke-dasharray", len);
  front.setAttribute("class", "prog");
  svg.append(back, front);
  return { svg, set: (frac, col) => { front.setAttribute("stroke-dashoffset", len * (1 - frac)); front.setAttribute("stroke", col); } };
}

// ---- pages ----
document.querySelectorAll(".tab").forEach((t) => t.onclick = () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("on", x === t));
  document.querySelectorAll(".page").forEach((p) => p.hidden = p.id !== t.dataset.page);
  if (t.dataset.page === "settings") loadSettings();
  if (t.dataset.page === "knowledge") loadKnowledge();
});

// ---- conversation ----
function organizerCommand(text) { api().submit(text); }
$("trackEvent").onsubmit = (e) => { e.preventDefault(); organizerCommand("track " + $("eventInput").value.trim()); $("eventInput").value = ""; };
$("makePlan").onsubmit = (e) => { e.preventDefault(); organizerCommand("plan: " + $("planInput").value.trim()); $("planInput").value = ""; };
function renderOrganizer(s) {
  for (const [id, rows, make, empty] of [
    ["eventCards", s.events || [], (r) => {
      const box = el("article", "organizerItem");
      box.append(el("b", "", r.title));
      box.append(el("p", "", r.kind === "exam" ? (r.happens ? "Exam reminder set" : "Exam date not known yet") : r.deadline ? "Registration reminder: " + new Date(r.deadline).toLocaleString([], {day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}) : "Deadline not known · reminder to check is set"));
      if (r.happens) box.append(el("p", "dim", "Event: " + new Date(r.happens).toLocaleDateString([], {day:"numeric",month:"long"})));
      const actions = el("div", "row wrap");
      const read = el("button", "ghost", "Read from a page"); read.onclick = () => {
        let help = box.querySelector('.screenHelp');
        if (!help) { help = el('p', 'screenHelp dim'); box.append(help); }
        help.textContent = 'Open the event page, then say “Jarvis, check deadline for ' + r.title + ' on this page”.';
      };
      const cancel = el("button", "ghost", "Remove"); cancel.onclick = () => organizerCommand("cancel event " + r.id);
      if (r.kind !== "exam") actions.append(read); actions.append(cancel); box.append(actions); return box;
    }, "Tell me about an event. I’ll keep its dates and remind you ahead of registration."],
    ["jobCards", s.jobs || [], (r) => {
      const box = el("article", "organizerItem"), steps = JSON.parse(r.steps), results = JSON.parse(r.results);
      box.append(el("b", "", r.request), el("p", "jobState", `${r.state} · ${r.cursor}/${steps.length} steps`));
      const list = el("ol", "planSteps");
      steps.forEach(([name,args], i) => { const li = el("li", i < r.cursor ? "finished" : "", name.replaceAll("_", " ") + ": " + Object.values(args).join(", ")); list.append(li); });
      box.append(list);
      if (results.length) box.append(el("p", "dim", results[results.length-1].reply));
      if (!["done","cancelled"].includes(r.state)) {
        const actions = el("div", "row"), run = el("button", "solid", r.state === "waiting" ? "Review in chat" : "Run plan"), cancel = el("button", "ghost", "Stop plan");
        run.onclick = () => { if (r.state === "waiting") { document.querySelector('[data-page="home"]').click(); $("input").focus(); } else organizerCommand("run plan " + r.id); };
        cancel.onclick = () => organizerCommand("stop plan " + r.id); actions.append(run,cancel); box.append(actions);
      }
      return box;
    }, "Ask for a plan. Nothing runs until you’ve seen the steps."]
  ]) {
    const root = $(id), key = JSON.stringify(rows);
    if (root.dataset.key === key) continue;
    root.dataset.key = key; root.replaceChildren();
    if (!rows.length) root.append(el("p", "empty organizerEmpty", empty));
    for (const row of rows) root.append(make(row));
  }
}

function addMsg(h) {
  const log = $("log"), atEnd = log.scrollHeight - log.scrollTop - log.clientHeight < 60;
  const [ts, who, text, tag] = h;
  const m = el("div", "msg " + tag);
  if (tag === "you") { m.textContent = text; m.append(el("span", "time", ts.slice(0, 5))); }
  else if (tag === "sys") m.textContent = `${ts}  ${who}: ${text}`;
  else { const w = el("span", "who", who); w.append(el("span", "time", ts.slice(0, 5))); m.append(w, document.createTextNode(text)); }
  log.append(m);
  while (log.children.length > 300) log.firstChild.remove();
  if (atEnd || tag === "you") log.scrollTop = log.scrollHeight;
}
$("details").onchange = (e) => { $("log").classList.toggle("details", e.target.checked); $("log").scrollTop = $("log").scrollHeight; };
$("say").onsubmit = (e) => { e.preventDefault(); const v = $("input").value.trim(); if (v) { api().submit(v); $("input").value = ""; } };
$("copy").onclick = () => {
  const ta = el("textarea");
  ta.value = history.map(([ts, who, text]) => `${ts} ${who}: ${text}`).join("\n");
  document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove();
  $("note").textContent = "Copied. Paste it to Claude with Ctrl+V.";
};
$("mic").onclick = () => api().toggle_mic();

// ---- orb, wave ----
const wave = $("wave"), bars = [];
for (let i = 0; i < 14; i++) { const b = el("i"); b.style.animationDelay = (i * 83 % 500) / 1000 + "s"; b.style.animationDuration = 0.7 + (i * 37 % 50) / 100 + "s"; wave.append(b); bars.push(b); }
function level(v) {   // called several times a second while the window is open
  $("meter").style.transform = `scaleX(${Math.min(1, v)})`;
  if (snap.state === "listening") bars.forEach((b, i) => b.style.transform = `scaleY(${Math.max(0.1, Math.min(1, v * (0.5 + 0.5 * Math.sin(Date.now() / 90 + i))))})`);
}

// ---- timers ----
function timerCard(t) {
  const c = el("article", "tcard"), head = el("div", "row between"), name = el("span", "name"), ends = el("span", "tiny dim");
  head.append(name, ends);
  const big = el("div", "bigRing"), r = ring(280, 128, 10, "#FFB547"), mid = el("div"), face = el("div", "bigClock"), status = el("div", "tiny dim");
  mid.append(face, status); big.append(r.svg, mid);
  const btns = el("div", "row btns");
  const reset = el("button", "round"), play = el("button", "round main"), plus = el("button", "round", "+1:00"), del = el("button", "round");
  reset.setAttribute("aria-label", "Reset"); del.setAttribute("aria-label", "Delete"); plus.setAttribute("aria-label", "Add one minute");
  reset.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 4v6h6"/><path d="M4.5 15a8 8 0 1 0 1.8-8.3L4 10"/></svg>';
  del.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  const id = t.id;
  reset.onclick = () => api().timer("reset", id); play.onclick = () => api().timer("toggle", id); plus.onclick = () => api().timer("plus", id); del.onclick = () => api().timer("delete", id);
  btns.append(reset, play, plus, del);
  c.append(head, big, btns);
  let wasOn = null;
  c.update = (x) => {
    name.textContent = x.name; ends.textContent = x.on ? "Ends " + x.ends : "Paused";
    face.textContent = clock(x.left); status.textContent = x.on ? "Running" : "Paused";
    r.set(x.left / x.total, x.left <= 60 ? "#FF7A59" : "#FFB547");
    if (x.on !== wasOn) {
      wasOn = x.on;
      play.setAttribute("aria-label", x.on ? "Pause" : "Start");
      play.innerHTML = x.on ? '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>' : '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5l11 7-11 7z"/></svg>';
    }
  };
  return c;
}
const ICONS = {
  x: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  done: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 13l4 4L19 7"/></svg>',
  pause: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>',
  play: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5l11 7-11 7z"/></svg>',
};
function tinyBtn(icon, label, fn) { const b = el("button", "tiny-btn"); b.innerHTML = ICONS[icon]; b.setAttribute("aria-label", label); b.onclick = fn; return b; }
function miniTimer(t) {
  const c = el("div", "mini"), box = el("div", "miniRing"), r = ring(112, 50, 6, "#FFB547"), face = el("div"), info = el("div", "tiny dim"), name = el("b");
  name.style.cssText = "display:block;font-weight:500;color:#E8EDF2;font-size:14px"; const ends = el("span"), acts = el("div", "acts");
  const play = tinyBtn("pause", "Pause", () => api().timer("toggle", t.id));
  acts.append(play, tinyBtn("x", "Delete timer", () => api().timer("delete", t.id)));
  info.append(name, ends, acts); box.append(r.svg, face); c.append(box, info);
  c.update = (x) => { name.textContent = x.name; ends.textContent = x.on ? "Ends " + x.ends : "Paused"; face.textContent = clock(x.left); r.set(x.left / x.total, x.left <= 60 ? "#FF7A59" : "#FFB547"); play.innerHTML = ICONS[x.on ? "pause" : "play"]; play.setAttribute("aria-label", x.on ? "Pause" : "Start"); };
  return c;
}
const minis = new Map();
function syncList(box, map, list, make) {
  const ids = new Set(list.map((t) => t.id));
  for (const [id, c] of map) if (!ids.has(id)) { c.remove(); map.delete(id); }
  for (const t of list) { if (!map.has(t.id)) { const c = make(t); map.set(t.id, c); box.prepend(c); } map.get(t.id).update(t); }
}
document.querySelectorAll(".chip").forEach((c) => c.onclick = () => api().add_timer(+c.dataset.secs));
$("custom").onsubmit = (e) => {
  e.preventDefault();
  const t = (+$("hrs").value || 0) * 3600 + (+$("mins").value || 0) * 60 + (+$("secs").value || 0);
  if (t > 0) { api().add_timer(Math.min(t, 86400)); ["hrs", "mins", "secs"].forEach((k) => $(k).value = ""); }
};
$("addRem").onsubmit = (e) => { e.preventDefault(); const v = $("remText").value.trim(); if (v) { api().add_reminder(v); $("remText").value = ""; } };
window.addEventListener("keydown", (e) => { if (e.key === "Tab") document.documentElement.classList.add("kb"); });
window.addEventListener("mousedown", () => document.documentElement.classList.remove("kb"));

// ---- everything else that Python sends ----
function update(s) {
  applyTheme(s.theme || 'light');
  renderOrganizer(s);
  const personal = $("personalCards"), personalKey = JSON.stringify(s.personal || []);
  if (personal.dataset.key !== personalKey) {
    personal.dataset.key = personalKey; personal.replaceChildren();
    for (const fact of s.personal || []) personal.append(factRow(fact));
    if (!(s.personal || []).length) personal.append(el("p", "empty", 'Say “remember my email is …” or “I am a CS student”.'));
  }
  snap = s;
  const cls = s.alert ? "alert" : s.booting ? "thinking" : s.state;
  $("orb").className = "orb " + (cls === "alert" ? "speaking alert" : cls);
  const w = WORDS[s.state] || WORDS.idle;
  $("stateTitle").textContent = s.booting ? "Starting up" : !s.mic && s.state === "idle" ? "Microphone off" : w[0];
  $("stateSub").textContent = s.booting ? "Getting my voice ready, sir. About 10 seconds." : s.state === "speaking" ? s.text : !s.mic && s.state === "idle" ? "Type below, or turn it back on" : w[1];
  if (s.listen_left > 0) $("stateSub").textContent = 'Go ahead, sir · ' + Math.ceil(s.listen_left) + ' seconds';
  wave.classList.toggle("talk", s.state === "speaking" || s.state === 'listening');
  if (s.state !== "listening" && s.state !== "speaking") bars.forEach((b) => b.style.transform = "");
  $("note").textContent = s.note;
  $("mic").textContent = s.mic ? "Microphone on" : "Microphone off";
  $("mic").classList.toggle("off", !s.mic);
  syncList($("timerCards"), cards, s.timers, timerCard);
  syncList($("sideTimers"), minis, s.timers, miniTimer);
  $("noTimers").hidden = s.timers.length > 0;
  $("timerCount").hidden = !s.timers.length; $("timerCount").textContent = s.timers.length;
  if (!s.timers.length) { if (!$("sideTimers").querySelector(".empty")) $("sideTimers").append(el("p", "empty", "None running, sir.")); }
  else $("sideTimers").querySelector(".empty")?.remove();
  const rem = $("sideRem"), key = JSON.stringify(s.reminders);
  if (rem.dataset.key !== key) {
    rem.dataset.key = key; rem.replaceChildren();
    if (!s.reminders.length) rem.append(el("p", "empty", "Nothing coming up, sir."));
    for (const r of s.reminders) {
      const d = el("div", "rem"), t = el("div");
      t.append(el("b", "", r.text), el("span", "", r.when));
      d.append(t, tinyBtn("done", "Mark done: " + r.text, () => api().reminder("done", r.id)), tinyBtn("x", "Cancel: " + r.text, () => api().reminder("delete", r.id)));
      rem.append(d);
    }
  }
  const a = s.alert, back = $("alert");
  if (a) {
    if (back.hidden || back.dataset.id !== String(a.id)) {
      back.hidden = false; back.dataset.id = a.id;
      $("alertTitle").textContent = a.title; $("alertSub").textContent = a.sub; $("alertFace").textContent = a.face;
      $("alertStop").textContent = a.kind === "timer" ? "Stop" : "Done";
    }
  } else back.hidden = true;
}
$("alertStop").onclick = () => api().alert("stop");
$("alertSnooze").onclick = () => api().alert("snooze");
function add(h) { history.push(h); addMsg(h); }

// ---- settings: every change saves itself ----
let settingsLoaded = false, saveTimer;
const percent = { s_tts_volume: (v) => Math.round(v * 100) + "%", s_tts_speed: (v) => (+v).toFixed(2) + "x" };
function showValues() { for (const id in percent) $("o" + id.slice(1)).textContent = percent[id]($(id).value); }
async function loadSettings() {
  const { cfg, voices, sites } = await api().settings();
  $("s_voice_on").checked = cfg.voice_on; $("s_speak_replies").checked = cfg.speak_replies; $("s_natural_replies").checked = cfg.natural_replies; $("s_start_with_windows").checked = cfg.start_with_windows;
  $("s_tts_volume").value = cfg.tts_volume; $("s_tts_speed").value = cfg.tts_speed; $("s_wake_replies").value = cfg.wake_replies.join("\n");
  showValues();
  const pick = $("s_tts_voice"); pick.replaceChildren();
  for (const [k, v] of Object.entries(voices)) { const o = el("option", "", v); o.value = k; pick.append(o); }
  pick.value = cfg.tts_voice;
  const box = $("browsers"); box.replaceChildren();
  for (const { key, name } of sites) {
    const row = el("div", "set"), label = el("span"), seg = el("div", "seg");
    label.append(el("b", "", name));
    seg.dataset.site = key; seg.dataset.value = cfg.browsers[key]; seg.setAttribute("role", "group"); seg.setAttribute("aria-label", name + " opens in");
    for (const [b, text] of [["edge", "Edge"], ["chrome", "Chrome"]]) {
      const btn = el("button", cfg.browsers[key] === b ? "on" : "", text);
      btn.type = "button";
      btn.onclick = () => { seg.dataset.value = b; seg.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === btn)); saveSoon(); };
      seg.append(btn);
    }
    row.append(label, seg); box.append(row);
  }
  settingsLoaded = true;
  await loadExtras();
}
function saveSoon() { showValues(); clearTimeout(saveTimer); saveTimer = setTimeout(saveNow, 350); }
async function saveNow() {
  if (!settingsLoaded) return;
  const browsers = {};
  document.querySelectorAll("#browsers .seg").forEach((s) => browsers[s.dataset.site] = s.dataset.value);
  $("saved").textContent = await api().save_settings({
    wake_replies: $("s_wake_replies").value.split("\n").map((x) => x.trim()).filter(Boolean), browsers,
    start_with_windows: $("s_start_with_windows").checked, tts_volume: +$("s_tts_volume").value, tts_speed: +$("s_tts_speed").value,
    voice_on: $("s_voice_on").checked, speak_replies: $("s_speak_replies").checked, natural_replies: $("s_natural_replies").checked, tts_voice: $("s_tts_voice").value,
  });
}
document.querySelectorAll(".settingsCol input, .settingsCol select, .settingsCol textarea").forEach((x) => x.addEventListener(x.type === "range" || x.tagName === "TEXTAREA" ? "input" : "change", saveSoon));
$("hear").onclick = () => api().hear_voice();
$("showDiagnostics").onclick = async () => {
  const d = await api().diagnostics(), box = $("diagnostics");
  box.hidden = false;
  box.textContent = d.heard ? `Heard: ${d.heard}\nOutcome: ${d.outcome}\n` +
    (d.steps || []).map(s => `${s.ok ? '✓' : '✗'} ${s.action}: ${s.result}`).join('\n') +
    `\nReply: ${d.reply}\n` + (d.timing ? `Prepare: ${d.timing.snapshot ?? '?'} ms · Understand: ${d.timing.resolve ?? '?'} ms · Act: ${d.timing.act} ms` : '') : 'No requests yet.';
};
$("manageFacts").onclick = () => document.querySelector('[data-page="knowledge"]').click();

// ---- what Jarvis knows: every line can be deleted ----
function kRows(box, rows, empty, make) {
  box.replaceChildren();
  if (!rows.length) { box.append(el("p", "empty", empty)); return; }
  for (const r of rows) box.append(make(r));
}
function kRow(text, small, onDelete) {
  const row = el("div", "set"), left = el("span"), b = el("b", "", text);
  left.append(b); if (small) left.append(el("small", "", small));
  row.append(left, tinyBtn("x", "Delete: " + text, onDelete));
  return row;
}
function applyTheme(theme) {
  const dark = theme === 'dark';
  if (document.documentElement.dataset.theme !== theme) document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  $("themeToggle").textContent = dark ? 'Light mode' : 'Dark mode';
  $("themeToggle").setAttribute('aria-label', 'Switch to ' + (dark ? 'light' : 'dark') + ' mode');
  try { localStorage.setItem('jarvis-theme', dark ? 'dark' : 'light'); } catch {}
}
$("themeToggle").onclick = async () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  applyTheme(theme);
  applyTheme(await api().set_theme(theme));
};
function factRow(fact) {
  const fields = factFields(fact.text);
  const row = el('div', 'factRow'), text = el('p', 'personalFact', fields.value), actions = el('div', 'factActions');
  const edit = el('button', 'ghost', 'Edit'), copy = el('button', 'ghost', 'Copy'), remove = el('button', 'ghost', 'Remove');
  copy.onclick = async () => { copy.textContent = await api().copy_note(fact.id) ? 'Copied' : 'Try again'; setTimeout(() => copy.textContent = 'Copy', 1800); };
  remove.onclick = async () => { await api().forget_note(fact.id); row.remove(); };
  edit.onclick = () => {
    if (row.querySelector('textarea')) return;
    actions.hidden = true;
    row.append(factEditor(fact, () => { actions.hidden = false; }));
  };
  actions.append(edit,copy,remove);
  if (fields.title) row.append(el('strong', 'factHeading', fields.title));
  if (fact.type) row.append(el('small','dim',`${fact.type} · ${fact.source || 'user'} · updated ${(fact.updated || '').slice(0,10)}`));
  if (fact.aliases?.length) row.append(el('small','dim','Also called: '+fact.aliases.join(', ')));
  row.append(text,actions); return row;
}
function factFields(text) {
  const match = /^my\s+(.{1,60}?)\s+(?:is|are)\s+([\s\S]+)$/i.exec(text || '');
  return match ? {title:match[1], value:match[2]} : {title:'', value:text || ''};
}
function factEditor(fact, onClose = () => {}) {
  const fields = factFields(fact?.text), form = el('form', 'factEditor');
  const titleLabel = el('label', '', 'Heading (optional)'), title = el('input');
  title.value = fields.title; title.maxLength = 60; title.placeholder = 'Personal Gmail, college email, course…';
  title.setAttribute('aria-label', 'Fact heading'); titleLabel.append(title);
  const valueLabel = el('label', '', 'What should I remember?'), value = el('textarea');
  value.value = fields.value; value.maxLength = 500; value.rows = 3; value.required = true;
  value.placeholder = 'Write your information here'; value.setAttribute('aria-label', 'Fact value'); valueLabel.append(value);
  const aliasLabel=el('label','','Alternate names (comma separated)'), aliases=el('input');
  aliases.value=(fact?.aliases || []).join(', '); aliases.maxLength=480; aliases.setAttribute('aria-label','Fact alternate names'); aliasLabel.append(aliases);
  const buttons = el('div', 'factEditorActions'), save = el('button', 'solid', 'Save fact'), cancel = el('button', 'ghost', 'Cancel'), feedback = el('span', 'tiny dim');
  cancel.type = 'button'; cancel.onclick = () => { form.remove(); onClose(); };
  feedback.setAttribute('role', 'status'); buttons.append(save,cancel); form.append(titleLabel,valueLabel,aliasLabel,buttons,feedback);
  form.onsubmit = async e => {
    e.preventDefault(); save.disabled = true;
    try {
      const result = await api().save_fact(fact?.id ?? null, title.value, value.value,aliases.value.split(',').map(s=>s.trim()).filter(Boolean));
      if (!result.ok) { feedback.textContent = result.message; return; }
      form.remove(); onClose(); update(result.snap);
      if (!$("knowledge").hidden) await loadKnowledge();
    } catch { feedback.textContent = 'Could not save. Your text is still here; please try again.'; }
    finally { save.disabled = false; }
  };
  setTimeout(() => title.focus(), 0);
  return form;
}
function addFactForm(id) {
  const box = $(id);
  if (box.querySelector('form')) { box.querySelector('input').focus(); return; }
  box.append(factEditor(null)); box.scrollIntoView({block:'nearest'});
}
$("addHomeFact").onclick = () => addFactForm('homeFactForm');
$("addFact").onclick = () => addFactForm('knowledgeFactForm');
$("allFacts").onclick = () => document.querySelector('[data-page="knowledge"]').click();
async function loadKnowledge() {
  const k = await api().knowledge();
  $("k_learn").checked = !k.paused;
  $("kstate").textContent = k.paused ? "Learning is paused" : "Learning is on";
  kRows($("k_words"), k.words, "Nothing yet. Correct me once and I remember.", (w) => kRow(`"${w.heard}" means ${w.name}`, w.source === "correction" ? "you corrected me" : `worked ${w.uses} times`, async () => { await api().forget_word(w.heard); loadKnowledge(); }));
  kRows($("k_usage"), k.usage, "Nothing counted yet.", (u) => { const r = el("div", "set"); r.append(el("span", "", u[0]), el("span", "tiny dim", u[1] + "x")); return r; });
  kRows($("k_habits"), k.habits, "None noticed yet. I only ask, I never act on my own.", (h) => kRow(h.text, h.answer === "no" ? "you said no: I won't ask again" : `seen on ${h.seen} days`, async () => { await api().forget_habit(h.pattern); loadKnowledge(); }));
  kRows($("k_routines"), k.routines, 'None yet. Add a routine above.', (r) => {
    const row=kRow(r.name,r.steps,async()=>{await api().forget_routine(r.name);loadKnowledge();});
    const controls=el('div','factActions'), edit=el('button','ghost','Edit'), run=el('button','ghost','Run');
    edit.onclick=()=>{$("routineName").value=r.name;$("routineSteps").value=r.sentences.join(' and then ');$("newRoutine").scrollIntoView({block:'nearest'});};
    run.onclick=()=>api().submit(r.name);controls.append(edit,run);
    if(r.state==='paused'){const resume=el('button','ghost','Resume');resume.onclick=()=>api().submit('resume routine '+r.name);controls.append(resume);}
    row.append(controls);return row;
  });
  const query=$("factSearch").value.trim().toLowerCase();
  kRows($("k_notes"), k.notes.filter(f=>[f.text,...(f.aliases || [])].join(' ').toLowerCase().includes(query)), "No matching facts.", factRow);
  resetWipe();
}
function resetWipe() {
  const box = $("k_wipe"), b = el("button", "ghost", "Forget everything…");
  b.onclick = () => {
    const yes = el("button", "solid", "Yes, forget it"), no = el("button", "ghost", "Keep it");
    yes.onclick = async () => { await api().forget_all(); loadKnowledge(); };
    no.onclick = resetWipe;
    box.replaceChildren(el("span", "tiny dim", "Sure, sir?"), yes, no);
  };
  box.replaceChildren(b);
}
$("k_learn").onchange = async (e) => { await api().set_learning(e.target.checked); loadKnowledge(); };
$("factSearch").oninput=loadKnowledge;
$("teachName").onsubmit=async e=>{e.preventDefault();$("nameFeedback").textContent=await api().teach_name($("heardName").value,$("actualName").value)?'Learned.':'Please use an installed app or known website name.';loadKnowledge();};
$("newRoutine").onsubmit=async e=>{e.preventDefault();const r=await api().save_routine($("routineName").value,$("routineSteps").value);$("routineFeedback").textContent=r.message;if(r.ok)loadKnowledge();};
const preferenceKeys=['quiet_enabled','quiet_start','quiet_end','cool_mode','daily_briefing','save_voice_clips'];
async function loadExtras(){const p=await api().preferences();for(const k of preferenceKeys){$(k).type==='checkbox'?$(k).checked=!!p[k]:$(k).value=p[k];}await listBackups();await googleStatus();}
async function listBackups(){const names=await api().backups();$("backupList").replaceChildren(...names.map(name=>{const o=el('option','',name);o.value=name;return o;}));}
$("savePreferences").onclick=async()=>{const p={};for(const k of preferenceKeys)p[k]=$(k).type==='checkbox'?$(k).checked:$(k).value;await api().preferences(p);$("preferencesFeedback").textContent='Saved.';};
$("backupNow").onclick=async()=>{try{$("backupFeedback").textContent='Saved: '+await api().create_backup();await listBackups();}catch{$("backupFeedback").textContent='Backup failed; your data was not replaced.';}};
$("restoreBackup").onclick=()=>{$("restoreConfirmation").hidden=!$("backupList").value;};
$("cancelRestore").onclick=()=>$("restoreConfirmation").hidden=true;
$("confirmRestore").onclick=async()=>{const r=await api().restore_backup($("backupList").value,true);$("backupFeedback").textContent=r.message;$("restoreConfirmation").hidden=true;await listBackups();};
async function googleStatus(){try{const s=await api().google_status();$("googleStatus").textContent=s.message;$("connectGoogle").disabled=s.busy;}catch{$("googleStatus").textContent='Google connection unavailable.';}}
$("connectGoogle").onclick=async()=>{$("googleStatus").textContent=await api().connect_google();};
$("refreshGoogle").onclick=googleStatus;
$("disconnectGoogle").onclick=async()=>{await api().disconnect_google();$("googleResults").textContent='';await googleStatus();};
async function readGoogle(service){const r=await api().read_google(service);$("googleResults").textContent=r.ok?(r.items.map(i=>i.title+' — '+(i.when||i.from||'')).join('\n')||'Nothing found.'):r.message;}
$("readGmail").onclick=()=>readGoogle('gmail');$("readCalendar").onclick=()=>readGoogle('calendar');
$("performanceCheck").onclick=async()=>{const p=await api().performance();$("performanceResult").textContent=`Memory including window: ${p.ram_mb} MB\nRequests measured: ${p.requests}\nTypical: ${p.median_ms??'—'} ms · Slowest 5% boundary: ${p.p95_ms??'—'} ms`+(p.last?`\nLast: prepare ${p.last.snapshot} ms, understand ${p.last.resolve} ms, act ${p.last.act} ms. Model: ${p.last.model}.`:'')+(p.speech?`\nLast voice: transcription ${p.speech.transcribe_ms} ms, end-to-delivery ${p.speech.delivery_ms} ms.`:'');};
$("assignmentForm").onsubmit=e=>{e.preventDefault();api().submit('assignment '+$("assignmentText").value+' due '+$("assignmentDue").value);};
$("repeatForm").onsubmit=e=>{e.preventDefault();api().submit('remind me '+$("repeatInterval").value+' at '+$("repeatTime").value+' to '+$("repeatText").value);};
$("briefingNow").onclick=()=>api().submit('daily briefing');
$("openDocument").onclick=async()=>{const r=await api().read_document();$("documentResult").textContent=r.ok?r.name+(r.truncated?' (excerpt)':'')+'\n\n'+r.text:r.message;};
$("refreshApps").onclick=async()=>{$("saved").textContent=await api().refresh_apps();};

window.jarvis = { update, add, level };
window.addEventListener("pywebviewready", async () => {
  const b = await api().boot();
  b.history.forEach(add);
  update(b.snap);
  $("log").scrollTop = $("log").scrollHeight;
});
