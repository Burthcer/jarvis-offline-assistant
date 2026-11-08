/* V4: the existing reactor circle, brought to life (the owner, 8 Nov: keep the circle, much more animation, theme colours only, no blob,
   no bars or lines when it speaks). Every frame each part moves on its own and reacts to state and to real sound:
     outer sweep and segment ring turn at their own speeds; the dial's ticks shimmer in travelling waves; the core breathes and glows;
     soft pulses ripple out from the core when he speaks (mic level) or Jarvis speaks (its real voice level), when it is called, and as a
     slow heartbeat at rest. Colours are only the reactor's own: cyan, its amber, and blue-grey when the microphone is off.
   Pauses when the window is hidden or minimised; with reduced motion it shows one still frame per state. */
(function () {
  const host = document.getElementById('orb');
  const svg = host && host.querySelector('.companionMark');
  if (!svg) return;
  const q = (s) => svg.querySelector(s), qa = (s) => [...svg.querySelectorAll(s)];
  const NS = 'http://www.w3.org/2000/svg';
  const parts = {
    ticks: qa('.reactorDial path'), sweep: q('.reactorSweep'), sweepArcs: qa('.reactorSweep path'), segs: q('.reactorSegments'),
    segArcs: qa('.reactorSegments path'), scan: q('.reactorScan'), pulse: q('.reactorPulse'), core: q('.reactorCore'), glyph: q('.reactorGlyph'),
    voice: q('.reactorVoice'), mute: q('.reactorMute'), dial: q('.reactorDial'),
  };
  if (parts.voice) parts.voice.style.display = 'none';                       // no bars, ever
  const halo = document.createElement('div'); halo.className = 'reactorHalo'; host.prepend(halo);
  const ripples = [0, 1, 2, 3].map(() => {                                   // a small pool of soft pulse rings
    const c = document.createElementNS(NS, 'circle');
    c.setAttribute('cx', 128); c.setAttribute('cy', 128); c.style.setProperty('fill', 'none'); c.style.setProperty('opacity', 0);
    parts.core.parentNode.insertBefore(c, parts.core);
    return { el: c, r: 0, a: 0 };
  });
  const segLen = parts.segArcs.map((p) => { try { return p.getTotalLength(); } catch { return 120; } });
  const tickAngle = parts.ticks.map((_, i) => i / parts.ticks.length * Math.PI * 2);

  const CYAN = [129, 234, 255], AMBER = [255, 189, 113], GREY = [110, 139, 161];
  // accent colour, energy, sweep / segment / scan turn speeds (degrees per second), tick waves per second, breath seconds, heartbeat seconds
  const MODES = {
    standby:   { col: CYAN,  e: .38, sw: 9,   sg: -4,   sc: 14,   wave: .18, breath: 5.5, beat: 4.5 },
    timer:     { col: AMBER, e: .42, sw: 22,  sg: -6,   sc: 18,   wave: .25, breath: 4.8, beat: 3.5 },
    ready:     { col: CYAN,  e: .72, sw: 38,  sg: -16,  sc: 60,   wave: .7,  breath: 3.0, beat: 0 },
    recording: { col: CYAN,  e: .85, sw: 52,  sg: -22,  sc: 110,  wave: 1.1, breath: 2.6, beat: 0 },
    question:  { col: AMBER, e: .7,  sw: 34,  sg: -14,  sc: 50,   wave: .6,  breath: 2.8, beat: 2.2 },
    decoding:  { col: CYAN,  e: .8,  sw: -90, sg: 70,   sc: -260, wave: 1.6, breath: 1.6, beat: 0 },
    thinking:  { col: CYAN,  e: .85, sw: -70, sg: 140,  sc: 220,  wave: 1.9, breath: 1.4, beat: 0 },
    speaking:  { col: CYAN,  e: .9,  sw: 30,  sg: -12,  sc: 40,   wave: .5,  breath: 2.4, beat: 0 },
    startup:   { col: CYAN,  e: .6,  sw: 120, sg: -60,  sc: 160,  wave: 2.2, breath: 1.2, beat: 0 },
    alert:     { col: AMBER, e: 1,   sw: 60,  sg: -30,  sc: 90,   wave: 1.4, breath: .9,  beat: .9 },
    'mic-off': { col: GREY,  e: .14, sw: 2,   sg: -1,   sc: 3,    wave: .05, breath: 8,   beat: 0 },
  };
  const now = () => performance.now() / 1000;
  const cur = { col: [...CYAN], e: .38, sw: 9, sg: -4, sc: 14, wave: .18, breath: 5.5, mic: 0, voice: 0 };
  const ang = { sw: 0, sg: 0, sc: 0, wave: 0, breath: 0 };
  let mode = 'standby', modeAt = now(), micTarget = 0, voiceTarget = 0, lastVoice = 0, lastMic = 0, nextBeat = now() + 2, lastGlow = '';

  function ripple(strength) {
    const free = ripples.find((p) => p.a <= 0) || ripples.reduce((a, b) => (a.r > b.r ? a : b));
    free.r = 50; free.a = Math.min(1, strength);
  }
  function setMode(m) {
    if (!MODES[m] || m === mode) return;
    if ((m === 'ready' || m === 'recording') && !['ready', 'recording', 'question'].includes(mode)) ripple(.9);   // called: a little inhale
    if (m === 'alert') ripple(1);
    mode = m; modeAt = now();
  }
  new MutationObserver(() => setMode(host.dataset.mode)).observe(host, { attributes: true, attributeFilter: ['data-mode'] });
  setMode(host.dataset.mode || 'standby');

  window.presence = {
    level(v) { micTarget = Math.max(0, Math.min(1, +v || 0)); },
    voice(v) { voiceTarget = Math.max(0, Math.min(1, +v || 0)); },
    get mode() { return mode; },
    snapshot() { return { mode, mic: cur.mic, voice: cur.voice, energy: cur.e, color: cur.col.map(Math.round), frames: this.frames }; },
    frames: 0,
  };

  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const paused = () => document.documentElement.hasAttribute('data-motion-paused') || document.hidden;
  const mix = (a, b, k) => a + (b - a) * k;
  const rgb = (c, a = 1) => `rgba(${c.map(Math.round).join(',')},${a})`;

  let last = now(), skip = 0, stillMode = null;
  function frame() {
    requestAnimationFrame(frame);
    if (paused()) return;
    if (reduced.matches) { if (stillMode !== mode) { stillMode = mode; draw(now(), 0); } return; }
    stillMode = null;
    const calm = mode === 'standby' || mode === 'mic-off' || mode === 'timer';
    if (calm && (skip++ % 3)) return;                                         // at rest: 20 frames a second, slow motion stays smooth, laptop stays cool
    const t = now(), dt = Math.min(.1, t - last); last = t;
    draw(t, dt);
  }

  function draw(t, dt) {
    const target = MODES[mode] || MODES.standby, k = dt ? 1 - Math.exp(-dt / .4) : 1;
    for (const key of ['e', 'sw', 'sg', 'sc', 'wave', 'breath']) cur[key] = mix(cur[key], target[key], k);
    cur.col = cur.col.map((v, i) => mix(v, target.col[i], k));
    const listening = mode === 'ready' || mode === 'recording' || mode === 'question';
    cur.mic = mix(cur.mic, listening ? micTarget : 0, dt ? 1 - Math.exp(-dt / .08) : 1);
    const vGoal = mode === 'speaking' ? voiceTarget : 0;
    cur.voice = mix(cur.voice, vGoal, dt ? 1 - Math.exp(-dt / (vGoal > cur.voice ? .05 : .16)) : 1);
    if (dt) {
      if (mode === 'speaking' && cur.voice - lastVoice > .1) ripple(.45 + cur.voice * .5);             // a syllable
      if (listening && cur.mic - lastMic > .14) ripple(.35 + cur.mic * .5);                             // his voice
      if (target.beat && t > nextBeat) { ripple(mode === 'alert' ? 1 : .32); nextBeat = t + target.beat; }   // heartbeat at rest
      ang.sw += dt * cur.sw * (1 + cur.voice * .6); ang.sg += dt * cur.sg * (1 + cur.mic * .8);
      ang.sc += dt * cur.sc; ang.wave += dt * cur.wave * Math.PI * 2; ang.breath += dt * Math.PI * 2 / cur.breath;
    }
    lastVoice = cur.voice; lastMic = cur.mic;
    const e = cur.e, life = Math.min(1, cur.mic * 1.3 + cur.voice), breath = Math.sin(ang.breath) * .5 + .5, col = cur.col;
    const boot = mode === 'startup' ? Math.min(1, (t - modeAt) / 1.4) : 1;

    // the whole instrument breathes, and swells a little with a voice
    svg.style.transform = `scale(${(1 + breath * .012 + life * .06).toFixed(4)})`;
    // the glow is a soft light BEHIND the circle (cheap to fade), not a blur filter redrawn every frame
    halo.style.opacity = (.25 + .45 * e * (.6 + .4 * breath) + .4 * life).toFixed(3);
    halo.style.transform = `scale(${(1.02 + .05 * breath + .12 * life).toFixed(4)})`;
    const tint = rgb(col.map(Math.round), 1);
    if (tint !== lastGlow) { halo.style.background = `radial-gradient(circle, ${rgb(col, .5)} 0%, ${rgb(col, .18)} 45%, transparent 70%)`; lastGlow = tint; }

    // rings turning at their own speeds
    parts.sweep.style.transform = `rotate(${(ang.sw % 360).toFixed(2)}deg)`;
    parts.segs.style.transform = `rotate(${(ang.sg % 360).toFixed(2)}deg) scale(${(1 + life * .035 + breath * .01).toFixed(4)})`;
    parts.scan.style.transform = `rotate(${(ang.sc % 360).toFixed(2)}deg)`;
    parts.sweepArcs[1] && parts.sweepArcs[1].style.setProperty('stroke', rgb(col));
    parts.sweepArcs[0] && parts.sweepArcs[0].style.setProperty('stroke', rgb(mode === 'mic-off' ? GREY : AMBER, .55 + .45 * e));
    parts.segs.style.setProperty('stroke', rgb(col, .55 + .45 * e));
    parts.segArcs.forEach((p, i) => {                                            // startup: the five segments light up one by one
      const on = Math.max(0, Math.min(1, boot * 5 - i));
      p.setAttribute('stroke-dasharray', `${segLen[i]}`); p.setAttribute('stroke-dashoffset', `${(segLen[i] * (1 - on)).toFixed(1)}`);
    });
    parts.scan.style.setProperty('stroke', rgb(col)); parts.scan.style.setProperty('opacity', (.3 + .6 * e).toFixed(3));

    // the dial's ticks: travelling waves of light (two when thinking), all brighter with a voice
    const waves = mode === 'thinking' || mode === 'decoding' ? 2 : 1;
    parts.dial.style.setProperty('stroke', rgb(col)); parts.dial.style.setProperty('opacity', 1);
    parts.ticks.forEach((p, i) => {
      let w = 0;
      for (let n = 0; n < waves; n++) w = Math.max(w, Math.max(0, Math.cos(tickAngle[i] - ang.wave - n * Math.PI)) ** 10);
      p.style.setProperty('opacity', (.18 + .22 * e + .55 * w * (.4 + e) + .35 * life).toFixed(3));
    });

    // pulses rippling out from the core
    for (const p of ripples) {
      if (p.a > 0 && dt) { p.r += dt * (34 + 30 * e); p.a -= dt * .75; }
      const a = Math.max(0, p.a) * Math.max(0, 1 - (p.r - 50) / 70);
      p.el.setAttribute('r', p.r.toFixed(1)); p.el.style.setProperty('stroke', rgb(col)); p.el.setAttribute('stroke-width', (2.5 - 1.5 * Math.min(1, (p.r - 50) / 70)).toFixed(2));
      p.el.style.setProperty('opacity', a.toFixed(3));
    }
    parts.pulse.style.setProperty('stroke', rgb(col)); parts.pulse.style.setProperty('opacity', (.15 + .35 * e * breath + .5 * life).toFixed(3));
    parts.pulse.setAttribute('r', (50 + breath * 2 + life * 6).toFixed(2));

    // the core: breathes, brightens with energy and voice
    const fill = [16, 43, 62].map((v, i) => mix(v, col[i], .08 + .22 * life + .06 * breath * e));
    parts.core.style.setProperty('fill', rgb(fill)); parts.core.style.setProperty('stroke', rgb(col));
    parts.core.setAttribute('stroke-width', (3 + 1.5 * life + breath * .6 * e).toFixed(2));
    parts.glyph.style.setProperty('stroke', rgb(mode === 'mic-off' ? GREY : col.map((v) => mix(v, 255, .25 * life))));
    parts.glyph.style.setProperty('opacity', (mode === 'mic-off' ? .4 : .8 + .2 * Math.max(breath, life)).toFixed(3));
    parts.mute.style.setProperty('opacity', mode === 'mic-off' ? 1 : 0);
    window.presence.frames++;
  }

  addEventListener('jarvismotionchange', () => draw(now(), 0));
  draw(now(), 0);
  requestAnimationFrame(frame);
})();
