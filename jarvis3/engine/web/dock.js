// Dock-style magnification (like the macOS dock): items grow as the mouse gets near, neighbours grow less with distance,
// items push each other apart so nothing overlaps, and everything follows the mouse with a soft spring.
// Only transforms are used (no layout change). Mouse only: touch, keyboard and reduced-motion users get the normal page.
// Adapted from devbhamaria.com/assets/js/dock-fx.js. Groups are LOCAL rows:
// controls in separate cards must never push one another.
(() => {
  const fine = matchMedia('(min-width: 0px)'), reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let GROUPS = [];
  const compact = matchMedia('(max-width: 760px), (hover: none)');   // fingers: the pop follows a touch instead of a mouse, gentler where items fill the row
  const CM = { header: .12, hero: .035, tabs: .05, arrows: .18, projbtn: .03, heroFoot: .08, principle: .08, toTop: .08 };
  const magOf = g => compact.matches && CM[g.name] != null ? CM[g.name] : g.mag;
  const K = 380, C = 24; // spring stiffness and damping (clearly under critical: the item overshoots a little, then settles = the pop)
  const bell = u => (u >= 1 ? 0 : (Math.cos(u * Math.PI) + 1) / 2);
  let px = -1e5, py = -1e5, raf = 0, last = 0;

  const init = () => {
    // Preserve spring state when facts/timers add buttons; resetting it while
    // an existing button is transformed would corrupt its measured position.
    const previous = new Map(GROUPS.flatMap(g => g.els.map((el,i) => [el,g.st[i]])));
    const rows = new Map();
    for (const el of document.querySelectorAll('button')) {
      const parent = el.parentElement;
      const local = parent.matches('.top nav,.quick,.factActions,.factEditorActions,.seg') ? parent : el;
      if (!rows.has(local)) rows.set(local, []);
      rows.get(local).push(el);
    }
    GROUPS = [...rows].map(([row,els]) => ({
      name: row.matches('.top nav') ? 'header' : 'controls',
      mag: row.matches('.top nav') ? .2 : .12, lift: 4, sharp: 1.5,
      radius: 60, core: .85, anchor: els.length > 1 ? 'center' : null, pad: 12,
      els, st: els.map(el => previous.get(el) || {m:0,v:0,tx:0,sc:1}), live:true
    }));
  };
  const settle = g => { g.els.forEach(el => { el.classList.remove('dock-live'); el.style.removeProperty('--sc'); el.style.removeProperty('--tx'); el.style.removeProperty('--ty'); el.style.removeProperty('--m'); }); g.st.forEach(s => { s.m = s.v = s.tx = 0; s.sc = 1; }); g.live = false; if (g.mirror) { const m = document.querySelector(g.mirror); if (m) ['--psc', '--ptx', '--pty'].forEach(k => m.style.removeProperty(k)); } };

  function frame(now) {
    raf = 0;
    const dt = Math.min(.034, (now - last) / 1000 || .016); last = now;
    const on = fine.matches && !reduced.matches && !window.jarvisMotionPaused && !document.hidden;
    let busy = false;
    const sx = scrollX, sy = scrollY;
    const plans = GROUPS.map(g => {
      if (!g.els.length) return null;
      if (!on) { if (g.live) settle(g); return null; }
      // cheap early exit: a group the mouse is nowhere near (and that is at rest) costs nothing this frame
      if (!g.live) {
        if (!g.cache || now - g.cache.t > 500) {     // page-coordinate box of the visible items, refreshed twice a second at most
          let l = 1e9, r = -1e9, t = 1e9, b = -1e9;
          for (const el of g.els) { const q = el.getBoundingClientRect(); if (!q.width) continue; l = Math.min(l, q.left + sx); r = Math.max(r, q.right + sx); t = Math.min(t, q.top + sy); b = Math.max(b, q.bottom + sy); }
          g.cache = { t: now, l, r, tp: t, b };
        }
        const m = g.pad + g.radius + 4, c = g.cache;
        if (px + sx < c.l - m || px + sx > c.r + m || py + sy < c.tp - m || py + sy > c.b + m) return null;
      }
      // READ: where each item would be with no transform (undo what we applied last frame)
      const base = g.els.map((el, i) => {
        const r = el.getBoundingClientRect(), s = g.st[i], w = r.width / s.sc, h = r.height / s.sc;
        if (!r.width) return { hidden: true, left: 0, w: 0, h: 0, cx: -1e5, cy: -1e5 }; // inside a hidden project
        const left = g.left ? r.left - s.tx : r.left + r.width / 2 - s.tx - w / 2;
        return { left, w, h, cx: left + w / 2, cy: r.top + r.height / 2 + g.lift * Math.max(0,s.m) };
      });
      const box = base.filter(r => !r.hidden).reduce((b, r) => ({ l: Math.min(b.l, r.left), r: Math.max(b.r, r.left + r.w), t: Math.min(b.t, r.cy - r.h / 2), b: Math.max(b.b, r.cy + r.h / 2) }), { l: 1e9, r: -1e9, t: 1e9, b: -1e9 });
      const inside = px > box.l - g.pad && px < box.r + g.pad && py > box.t - g.pad && py < box.b + g.pad;
      return { g, base, inside };
    });
    for (const p of plans) {
      if (!p) continue;
      const { g, base, inside } = p;
      // spring each item toward its target magnification
      g.st.forEach((s, i) => {
        const b = base[i];
        if (b.hidden) { s.m = s.v = 0; return; }
        const dx = Math.max(0, Math.abs(px - b.cx) - (b.w / 2) * g.core), dy = Math.max(0, Math.abs(py - b.cy) - (b.h / 2) * g.core);
        const target = inside ? Math.pow(bell(Math.hypot(dx, dy) / g.radius), g.sharp || 1) : 0;
        s.v += (K * (target - s.m) - C * s.v) * dt; s.m += s.v * dt;
        if (!inside && Math.abs(s.m) < .0006 && Math.abs(s.v) < .002) { s.m = 0; s.v = 0; }
      });
      const gm = magOf(g), grow = g.st.map((s, i) => base[i].w * gm * Math.max(0, s.m));
      const rows = []; // items on the same visual row push each other along that row
      base.forEach((b, i) => { if (b.hidden) return; let r = rows.find(r => Math.abs(r.cy - b.cy) < 10); if (!r) rows.push(r = { cy: b.cy, idx: [] }); r.idx.push(i); });
      const tx = g.st.map(() => 0);
      if (g.anchor) for (const r of rows) {
        const order = r.idx.slice().sort((a, b) => base[a].left - base[b].left), E = order.reduce((s, i) => s + grow[i], 0);
        let before = 0; for (const i of order) { tx[i] = before + grow[i] / 2 - (g.anchor === 'end' ? E : g.anchor === 'center' ? E / 2 : 0); before += grow[i]; }
      }
      // WRITE
      let any = inside;
      g.st.forEach((s, i) => {
        const m = Math.max(0, s.m); s.sc = 1 + gm * m; s.tx = tx[i];
        const el = g.els[i];
        if (!el.classList.contains('dock-live')) el.classList.add('dock-live');
        el.style.setProperty('--sc', s.sc.toFixed(4)); el.style.setProperty('--tx', s.tx.toFixed(2) + 'px'); el.style.setProperty('--ty', (-g.lift * m).toFixed(2) + 'px'); el.style.setProperty('--m', Math.min(1, m).toFixed(4));
        if (g.mirror && el.classList.contains('on')) { const pill = document.querySelector(g.mirror); if (pill) { pill.style.setProperty('--psc', s.sc.toFixed(4)); pill.style.setProperty('--ptx', s.tx.toFixed(2) + 'px'); pill.style.setProperty('--pty', (-g.lift * m).toFixed(2) + 'px'); } }
        if (m > 0 || Math.abs(s.v) > 0) any = true;
      });
      g.live = true;
      if (!any) settle(g); else busy = true;
    }
    if (busy) raf = requestAnimationFrame(frame);
  }
  const wake = () => { if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); } };

  init();
  new MutationObserver(changes => {
    if (changes.some(c => [...c.addedNodes, ...c.removedNodes].some(n => n.nodeType === 1 && (n.matches?.('button') || n.querySelector?.('button'))))) {
      init(); wake();
    }
  }).observe(document.body, {childList:true, subtree:true});
  addEventListener('pointermove', e => { px = e.clientX; py = e.clientY; wake(); }, { passive: true });
  addEventListener('pointerdown', e => { if (e.pointerType === 'mouse') return; px = e.clientX; py = e.clientY; wake(); }, { passive: true });
  const lift = e => { if (e.pointerType === 'mouse') return; setTimeout(() => { px = py = -1e5; wake(); }, 120); };   // let the pop show on a quick tap, then spring back
  addEventListener('pointerup', lift, { passive: true }); addEventListener('pointercancel', lift, { passive: true });
  addEventListener('scroll', () => { for (const g of GROUPS) g.cache = null; wake(); }, { passive: true, capture: true });
  addEventListener('resize', wake, { passive: true });
  addEventListener('jarvismotionchange', wake);
  document.documentElement.addEventListener('mouseleave', () => { px = py = -1e5; wake(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { px = py = -1e5; wake(); } });
})();
