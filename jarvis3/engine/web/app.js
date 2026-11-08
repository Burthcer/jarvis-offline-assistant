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
  if (t.dataset.page === "routines") loadKnowledge();
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

// ---- reactor ----
function level(v) {   // called several times a second while the window is open
  const strength = Math.max(0, Math.min(1, v));
  $("meter").style.transform = `scaleX(${strength})`;
  if (snap.state === 'listening' && snap.mic && !snap.mic_paused && !document.documentElement.hasAttribute('data-motion-paused'))
    $("orb").style.setProperty('--reactor-level', 1 + strength * .12);
  window.presence && window.presence.level(strength);
}
function voice(v) {   // Jarvis's own voice loudness while it speaks (V4): the living presence pulses with it
  window.presence && window.presence.voice(v);
}
function pauseMotion() {
  document.documentElement.toggleAttribute('data-motion-paused', document.hidden || !!window.jarvisMotionPaused);
  if (document.documentElement.hasAttribute('data-motion-paused')) $("orb").style.removeProperty('--reactor-level');
}
document.addEventListener('visibilitychange', pauseMotion);
addEventListener('jarvismotionchange', pauseMotion);
pauseMotion();

function reactorMode(s) {
  if (s.alert) return 'alert';
  if (s.booting) return 'startup';
  if (s.state === 'speaking') return 'speaking';
  if (s.state === 'thinking') return s.capture_phase === 'decoding' ? 'decoding' : 'thinking';
  if (s.state === 'listening') {
    if (s.capture_phase === 'recording') return 'recording';
    return s.awaiting_answer ? 'question' : 'ready';
  }
  if (!s.mic || s.mic_paused) return 'mic-off';
  return s.timers.some(t => t.on) ? 'timer' : 'standby';
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
    for (const fact of s.personal || []) {
      const fields = factFields(fact.text, fact.literal), preview = el('div', 'homeFact');
      if (fields.title) preview.append(el('strong', '', fields.title));
      preview.append(el('p', '', fields.value));
      personal.append(preview);
    }
    $("homeFactCount").textContent = (s.personal || []).length ? `${s.personal.length} shown` : 'Empty';
    if (!(s.personal || []).length) personal.append(el("p", "empty", 'Use Knowledge to add a fact.'));
  }
  snap = s;
  const cls = s.alert ? "alert" : s.booting ? "thinking" : s.state;
  $("orb").className = "orb " + (cls === "alert" ? "speaking alert" : cls);
  $("orb").dataset.mode = reactorMode(s);
  if (s.state !== 'listening' || !s.mic || s.mic_paused) $("orb").style.removeProperty('--reactor-level');
  const w = WORDS[s.state] || WORDS.idle;
  $("stateTitle").textContent = s.booting ? "Starting up" : !s.mic && s.state === "idle" ? "Microphone off" : w[0];
  $("stateSub").textContent = s.booting ? "Getting my voice ready, sir. About 10 seconds." : s.state === "speaking" ? s.text : !s.mic && s.state === "idle" ? "Type below, or turn it back on" : w[1];
  if (s.mic_paused && s.state === 'idle') {
    $("stateTitle").textContent = 'Microphone paused';
    $("stateSub").textContent = 'You can still type a command below';
  }
  if (s.state === 'listening' && s.listen_left > 0) {
    $("stateSub").textContent = s.hands_free_active
      ? 'Hands-free · ' + clock(Math.ceil(s.listen_left)) + ' left'
      : 'Go ahead, sir · ' + Math.ceil(s.listen_left) + ' seconds';
  }
  const voiceStatus = s.booting ? 'Starting' : !s.mic ? 'Mic off' : s.mic_paused ? 'Mic paused' : s.state === 'thinking' ? 'Thinking' :
    s.state === 'speaking' ? 'Speaking' : s.hands_free_active ? 'Hands-free · ' + clock(Math.ceil(s.listen_left)) :
    s.state === 'listening' ? 'Listening' : 'Say “Jarvis”';
  $("note").textContent = voiceStatus;
  $("note").title = s.note || voiceStatus;
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
  await loadV3();
  await loadWorkspaces();
  await loadMusic();
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
document.querySelectorAll("#settings [id^=s_]").forEach((x) => x.addEventListener(x.type === "range" || x.tagName === "TEXTAREA" ? "input" : "change", saveSoon));
$("hear").onclick = () => api().hear_voice();
$("showDiagnostics").ontoggle = async e => {
  if (!e.target.open) return;
  const d = await api().diagnostics(), box = $("diagnostics");
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
  const fields = factFields(fact.text,fact.literal);
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
function factFields(text,literal=false) {
  if(literal)return {title:'',value:text||''};
  const match = /^my\s+(.{1,60}?)\s+(?:is|are)\s+([\s\S]+)$/i.exec(text || '');
  return match ? {title:match[1], value:match[2]} : {title:'', value:text || ''};
}
function factEditor(fact, onClose = () => {}, link = false) {
  const fields = factFields(fact?.text,fact?.literal), form = el('form', 'factEditor');
  const titleLabel = el('label', '', link ? 'What should Jarvis call this link?' : 'What is it? (short name, optional)'), title = el('input');
  title.value = fields.title; title.maxLength = 60; title.placeholder = 'email, PIN code, college, blood group…';
  title.setAttribute('aria-label', 'Fact heading'); titleLabel.append(title);
  const valueLabel = el('label', '', link ? 'Website address' : 'The information'), value = el('textarea');
  value.value = fields.value; value.maxLength = 4096; value.rows = 3; value.required = true;
  value.placeholder = 'Write your information here'; value.setAttribute('aria-label', 'Fact value'); valueLabel.append(value);
  const aliasLabel=el('label','','Alternate names (comma separated)'), aliases=el('input');
  aliases.value=(fact?.aliases || []).join(', '); aliases.maxLength=480; aliases.setAttribute('aria-label','Fact alternate names'); aliasLabel.append(aliases);
  if (link) {
    title.required = true; title.placeholder = 'Dashboard';
    value.rows = 1; value.placeholder = 'https://example.com/dashboard';
  }
  const buttons = el('div', 'factEditorActions'), save = el('button', 'solid', link ? 'Save link' : 'Save fact'), cancel = el('button', 'ghost', 'Cancel'), feedback = el('span', 'tiny dim');
  cancel.type = 'button'; cancel.onclick = () => { form.remove(); onClose(); };
  feedback.setAttribute('role', 'status'); buttons.append(save,cancel); form.append(titleLabel,valueLabel,aliasLabel,buttons,feedback);
  form.onsubmit = async e => {
    e.preventDefault(); save.disabled = true;
    try {
      // Textareas normalise line endings. Keep the original bytes on an unchanged edit.
      const content = value.value === fields.value.replace(/\r\n?/g,'\n') ? fields.value : value.value;
      const result = await api().save_fact(fact?.id ?? null, title.value, content,aliases.value.split(',').map(s=>s.trim()).filter(Boolean), link);
      if (!result.ok) { feedback.textContent = result.message; return; }
      form.remove(); onClose(); update(result.snap);
      if (!$("knowledge").hidden) await loadKnowledge();
    } catch { feedback.textContent = 'Could not save. Your text is still here; please try again.'; }
    finally { save.disabled = false; }
  };
  setTimeout(() => title.focus(), 0);
  return form;
}
function addKnowledge(button, link) {
  const box = $('knowledgeFactForm'), buttons = [$('addFact'), $('addLink')];
  if (box.querySelector('form')) return;
  buttons.forEach(b => b.hidden = true);
  button.setAttribute('aria-expanded', 'true');
  box.append(factEditor(null, () => {
    buttons.forEach(b => b.hidden = false);
    button.setAttribute('aria-expanded', 'false');
    button.focus();
  }, link));
}
$("addFact").onclick = () => addKnowledge($("addFact"), false);
$("addLink").onclick = () => addKnowledge($("addLink"), true);
$("allFacts").onclick = () => document.querySelector('[data-page="knowledge"]').click();
async function loadKnowledge() {
  const k = await api().knowledge();
  $("k_learn").checked = !k.paused;
  $("kstate").textContent = k.paused ? "Learning is paused" : "Learning is on";
  kRows($("k_words"), k.words, "Nothing yet. Correct me once and I remember.", (w) => kRow(`"${w.heard}" means ${w.name}`, w.source === "correction" ? "you corrected me" : `worked ${w.uses} times`, async () => { await api().forget_word(w.heard); loadKnowledge(); }));
  kRows($("k_usage"), k.usage, "Nothing counted yet.", (u) => { const r = el("div", "set"); r.append(el("span", "", u[0]), el("span", "tiny dim", u[1] + "x")); return r; });
  kRows($("k_habits"), k.habits, "None noticed yet. I only ask, I never act on my own.", (h) => kRow(h.text, h.answer === "no" ? "you said no: I won't ask again" : `seen on ${h.seen} days`, async () => { await api().forget_habit(h.pattern); loadKnowledge(); }));
  kRows($("k_routines"), k.routines, 'None yet. Make one above.', (r) => {
    const card = el('article', 'routineCard card'), header = el('div', 'row between');
    header.append(el('h2', 'routineTitle', r.name), el('span', 'tiny dim', `${r.pills.length} ${r.pills.length === 1 ? 'step' : 'steps'}`));
    const steps = el('ol', 'routineSummary');
    for (const step of r.pills) {
      const chip = el('li', 'routineChip', step.text);
      chip.dataset.kind = step.kind;
      steps.append(chip);
    }
    const controls = el('div', 'row wrap routineControls');
    const run = el('button', 'solid', r.state === 'paused' ? 'Resume' : 'Start');
    run.onclick = () => api().submit(`${r.state === 'paused' ? 'resume' : 'start'} routine ${r.name}`);
    const close = el('button', 'ghost', 'Close all'), edit = el('button', 'ghost', 'Edit');
    close.onclick = () => api().submit(`close routine ${r.name}`);
    edit.onclick = () => openRoutineEditor(r);
    controls.append(run, close, edit);
    if (r.state === 'paused') {
      const restart = el('button', 'ghost', 'Start over');
      restart.onclick = () => api().submit(`start routine ${r.name}`);
      controls.append(restart);
    }
    const remove = el('button', 'ghost routineRemove', 'Delete');
    remove.onclick = () => {
      const confirm = el('button', 'ghost', 'Delete routine'), cancel = el('button', 'ghost', 'Keep it');
      confirm.onclick = async () => { await api().forget_routine(r.name); await loadKnowledge(); };
      cancel.onclick = () => footer.replaceChildren(remove);
      footer.replaceChildren(el('span', 'tiny dim', `Delete ${r.name}?`), confirm, cancel);
    };
    const footer = el('div', 'row wrap routineFooter');
    footer.append(remove);
    card.append(header, steps, controls, footer);
    return card;
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
let routineRevision = null;

function addRoutinePill(kind, text = '', index = null) {
  const list = $('routinePills'), pill = el('li', 'routinePill'), input = el('input');
  const label = {app:'Open', command:'Command', saved:'Saved action'}[kind];
  pill.dataset.kind = kind;
  if (index !== null) pill.dataset.index = index;
  input.value = text;
  input.maxLength = 200;
  input.readOnly = kind === 'saved';
  input.required = true;
  input.placeholder = kind === 'app' ? 'e.g. YouTube' : 'e.g. Set a timer for 25 minutes';
  input.setAttribute('aria-label', `${label} step`);
  const remove = el('button', 'routinePillRemove', '×');
  remove.type = 'button';
  remove.setAttribute('aria-label', `Remove ${label.toLowerCase()} step`);
  remove.onclick = () => {
    const neighbor = pill.nextElementSibling || pill.previousElementSibling;
    pill.remove();
    (neighbor?.querySelector('input') || $('addRoutineApp')).focus();
  };
  pill.append(el('span', 'routinePillLabel', label), input, remove);
  list.append(pill);
  return input;
}

function openRoutineEditor(routine = null) {
  routineRevision = routine?.revision ?? null;
  $('routineName').value = routine?.name ?? '';
  $('routineName').readOnly = !!routine;
  $('routineEditorTitle').textContent = routine ? `Edit ${routine.name}` : 'New routine';
  $('routineFeedback').textContent = '';
  $('routinePills').replaceChildren();
  for (const step of routine?.pills || []) addRoutinePill(step.kind, step.text, step.index);
  $('routineEditor').showModal();
  (routine ? $('routinePills').querySelector('input') || $('addRoutineApp') : $('routineName')).focus();
}

$('createRoutine').onclick = () => openRoutineEditor();
$('addRoutineApp').onclick = () => addRoutinePill('app').focus();
$('addRoutineCommand').onclick = () => addRoutinePill('command').focus();
$('cancelRoutine').onclick = () => $('routineEditor').close();
$('routineEditor').oncancel = e => { if ($('saveRoutine').disabled) e.preventDefault(); };
$('newRoutine').onsubmit = async e => {
  e.preventDefault();
  const save = $('saveRoutine'), cancel = $('cancelRoutine'), feedback = $('routineFeedback');
  if (save.disabled) return;
  const entries = [...$('routinePills').children].map(pill => {
    const entry = {kind:pill.dataset.kind, text:pill.querySelector('input').value};
    if (pill.dataset.index !== undefined) entry.index = Number(pill.dataset.index);
    return entry;
  });
  if (!entries.length) { feedback.textContent = 'Add an app, website or command first.'; return; }
  const fields = $('newRoutine').querySelector('.routineEditorSteps'), name = $('routineName');
  save.disabled = cancel.disabled = true;
  fields.inert = name.disabled = true;
  feedback.textContent = 'Checking steps…';
  try {
    const result = await api().save_routine_pills(name.value, routineRevision, entries);
    if (!result.ok) { feedback.textContent = result.message; return; }
    $('routineEditor').close();
    $('routineState').textContent = result.message;
    loadKnowledge().catch(() => { $('routineState').textContent = result.message + ' Reopen Routines to refresh the list.'; });
  } catch { feedback.textContent = 'Could not save the routine. Please try again.'; }
  finally { save.disabled = cancel.disabled = fields.inert = name.disabled = false; }
};
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

function voicePreferences(values){for(const k of ['tts_speed','tts_volume'])if(typeof values[k]==='number')$('s_'+k).value=values[k];showValues();}
window.jarvis = { update, add, level, voice, voicePreferences };
let workspaceFolders=[];
async function loadMusic(values){const r=await api().music_settings(values);$('musicFeedback').textContent=r.message;if(r.ok){$('musicUrl').value=r.url;$('musicBrowser').value=r.browser;}}
$('musicForm').onsubmit=async e=>{e.preventDefault();await loadMusic({url:$('musicUrl').value,browser:$('musicBrowser').value});};
function renderWorkspaceFolders(){const box=$('workspaceFolders');box.replaceChildren();for(const path of workspaceFolders){const row=el('div','set'),remove=el('button','ghost','Remove');remove.type='button';remove.setAttribute('aria-label','Remove folder '+path);remove.onclick=()=>{workspaceFolders=workspaceFolders.filter(p=>p!==path);renderWorkspaceFolders();};row.append(el('span','tiny',path),remove);box.append(row);}}
$('chooseWorkspaceFolder').onclick=async()=>{const button=$('chooseWorkspaceFolder');button.disabled=true;try{const path=await api().choose_workspace_folder();if(path&&!workspaceFolders.includes(path)){workspaceFolders.push(path);renderWorkspaceFolders();}}catch{$('workspaceFeedback').textContent='Could not choose that folder.';}finally{button.disabled=false;}};
async function loadWorkspaces(){const rows=await api().workspaces();$('workspaceList').replaceChildren();for(const r of rows){const box=el('div','set'),label=el('span','',r.name+' · '+r.state+(r.aliases?.length?' · '+r.aliases.join(', '):'')),edit=el('button','ghost','Edit'),run=el('button','ghost','Start');edit.onclick=()=>{$('workspaceName').value=r.name;$('workspaceAliases').value=(r.aliases||[]).join(', ');$('workspaceApps').value=r.apps.join('\n');$('workspaceUrls').value=r.urls.join('\n');$('workspaceBrowser').value=r.browser;workspaceFolders=[...(r.folders||[])];renderWorkspaceFolders();};run.onclick=()=>api().submit('start workspace '+r.name);box.append(label,edit,run);$('workspaceList').append(box);}}
$('workspaceForm').onsubmit=async e=>{e.preventDefault();const lines=id=>$(id).value.split('\n').map(s=>s.trim()).filter(Boolean);const r=await api().save_workspace($('workspaceName').value,lines('workspaceApps'),lines('workspaceUrls'),$('workspaceBrowser').value,workspaceFolders,$('workspaceAliases').value.split(',').map(s=>s.trim()).filter(Boolean));$('workspaceFeedback').textContent=r.message;await loadWorkspaces();};
async function loadV3(values){const s=await api().v3_status(values);$("v3Cues").checked=s.audible_cues;$("v3Prefix").checked=s.prefix_wake;for(const [id,key] of Object.entries({v3Followups:'conversation_followups',v3Arrival:'arrival_greeting',v3Minimal:'minimal_feedback',v3Dnd:'do_not_disturb',v3Interrupts:'early_interrupts',v3Clipboard:'clipboard_context'}))$(id).checked=s[key];$("v3Voice").checked=s.only_my_voice;$("v3Camera").checked=s.camera_arrival;$("v3HandsFree").value=s.hands_free_minutes;$("v3VoiceStatus").textContent='Right now: voice check '+s.voice+' · camera '+s.camera;}
for(const [id,key] of Object.entries({v3Followups:'conversation_followups',v3Arrival:'arrival_greeting',v3Minimal:'minimal_feedback',v3Dnd:'do_not_disturb',v3Interrupts:'early_interrupts',v3Clipboard:'clipboard_context'}))$(id).onchange=e=>loadV3({[key]:e.target.checked});
$("v3Voice").onchange=e=>loadV3({only_my_voice:e.target.checked});$("v3Camera").onchange=e=>loadV3({camera_arrival:e.target.checked});$("v3HandsFree").onchange=e=>loadV3({hands_free_minutes:Number(e.target.value)||0});
$("v3Cues").onchange=e=>loadV3({audible_cues:e.target.checked});
$("v3Prefix").onchange=e=>loadV3({prefix_wake:e.target.checked});
document.querySelectorAll('.jump button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.jump button').forEach(x=>{
    x.classList.toggle('on',x===b);
    x.setAttribute('aria-pressed',String(x===b));
  });
  document.querySelectorAll('.settingsGroup').forEach(g=>g.hidden=g.id!==b.dataset.to);
  $('settings').scrollTop=0;
});
document.querySelector('.jump button').click();
$("refreshV3").ontoggle = async e => {
  if (!e.target.open) return;
  const s = await api().v3_status();
  $("v3Status").textContent = [s.phase, ...s.events.map(row => `${row.request} · ${row.event}`)].join('\n');
};
window.addEventListener("pywebviewready", async () => {
  const b = await api().boot();
  b.history.forEach(add);
  update(b.snap);
  $("log").scrollTop = $("log").scrollHeight;
});
