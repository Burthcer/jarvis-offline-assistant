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
});

// ---- conversation ----
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
  snap = s;
  const cls = s.alert ? "alert" : s.booting ? "thinking" : s.state;
  $("orb").className = "orb " + (cls === "alert" ? "speaking alert" : cls);
  const w = WORDS[s.state] || WORDS.idle;
  $("stateTitle").textContent = s.booting ? "Starting up" : !s.mic && s.state === "idle" ? "Microphone off" : w[0];
  $("stateSub").textContent = s.booting ? "Getting my voice ready, sir. About 10 seconds." : s.state === "speaking" ? s.text : !s.mic && s.state === "idle" ? "Type below, or turn it back on" : w[1];
  wave.classList.toggle("talk", s.state === "speaking");
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

window.jarvis = { update, add, level };
window.addEventListener("pywebviewready", async () => {
  const b = await api().boot();
  b.history.forEach(add);
  update(b.snap);
  $("log").scrollTop = $("log").scrollHeight;
});
