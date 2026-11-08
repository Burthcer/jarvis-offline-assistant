// Page background: a slowly flowing dithered pattern (like a halftone print) plus a pixel trail that lights up under the mouse.
// Both are drawn on fixed canvases behind the whole page, take their colours from the site's own theme colours (light and dark),
// pause in a hidden tab, and stay still for people who asked for reduced motion. The trail is for a mouse only (no touch).
(() => {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const fine = matchMedia('(hover: hover) and (pointer: fine)');
  const root = document.documentElement;

  const mk = cls => { const c = document.createElement('canvas'); c.className = cls; c.setAttribute('aria-hidden', 'true'); document.body.prepend(c); return c; };
  const bg = mk('page-dither'), trail = mk('page-trail');
  const bctx = bg.getContext('2d'), tctx = trail.getContext('2d');
  if (!bctx || !tctx) return;

  // any CSS colour -> [r,g,b]
  const probe = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
  const rgb = value => { probe.clearRect(0, 0, 1, 1); probe.fillStyle = '#000'; probe.fillStyle = value; probe.fillRect(0, 0, 1, 1); const d = probe.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2]]; };
  const lift = (c, k) => c.map(v => Math.round(v + (255 - v) * k));
  let blue = [40, 82, 150], dark = false, trailColors = [blue, blue];
  const readTheme = () => {
    dark = root.dataset.theme === 'dark';
    try { blue = rgb(getComputedStyle(root).getPropertyValue('--blue').trim() || '#285296'); } catch {}
    // the trail stays in the theme's own blue: deep blue tones on light, soft blue tones on dark
    trailColors = dark ? [blue, lift(blue, .35), lift(blue, .6)] : [[28, 35, 40], blue, [60, 100, 170]];
    setPalette(); buildTrailTable(); paintBg(performance.now());
  };

  // ---------------- animated dither ----------------
  // Cheap on purpose: the flowing field is only computed on a coarse grid (a few thousand points) and blended up to every dot,
  // dots are written as whole 32-bit pixels, and the frame rate is capped (lower on phones).
  const bayer = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
  const thr = new Float32Array(16).map((_, i) => (bayer[i] / 16 - .5) * .9);
  const LEVELS = 5, K = 6;                           // K = dots per coarse grid step
  let cell = 4, bw = 0, bh = 0, img = null, px32 = null, running = false, last = 0, interval = 50;
  let gw = 0, gh = 0, field = null, colIdx = null, colFrac = null;
  let pal = new Uint32Array(LEVELS);
  const little = new Uint8Array(new Uint32Array([1]).buffer)[0] === 1;
  const pack = (r, g, b, a) => little ? ((a << 24) | (b << 16) | (g << 8) | r) >>> 0 : ((r << 24) | (g << 16) | (b << 8) | a) >>> 0;
  const setPalette = () => { const k = innerWidth < 760 ? .55 : 1, a = dark ? [0, 20, 42, 68, 100] : [0, 9, 20, 33, 48]; pal = Uint32Array.from(a, v => pack(blue[0], blue[1], blue[2], Math.round(v * k))); };   // calmer on phones, where text sits closer to the pattern
  const sizeBg = () => {
    const phone = innerWidth < 760;
    cell = phone ? 4 : 3; interval = phone ? 80 : 50;
    bw = Math.max(8, Math.ceil(innerWidth / cell)); bh = Math.max(8, Math.ceil(innerHeight / cell));
    bg.width = bw; bg.height = bh;
    img = bctx.createImageData(bw, bh); px32 = new Uint32Array(img.data.buffer);
    gw = Math.ceil(bw / K) + 1; gh = Math.ceil(bh / K) + 1; field = new Float32Array(gw * gh);
    colIdx = new Int32Array(bw); colFrac = new Float32Array(bw);
    for (let x = 0; x < bw; x++) { colIdx[x] = Math.floor(x / K); colFrac[x] = (x % K) / K; }
  };
  function paintBg(now) {
    if (!img) return;
    const t = now * 0.00009, aspect = (bw / bh) * .55, sx = 5.2 / bw, sy = 3.4 / bh;
    for (let j = 0; j < gh; j++) {                    // the flowing field, on the coarse grid only
      const fy = j * K * sy * aspect;
      for (let i = 0; i < gw; i++) {
        const fx = i * K * sx;
        const wx = fx + Math.sin(fy * 1.3 + t * 5.1) * .9, wy = fy + Math.cos(fx * 1.1 - t * 4.3) * .9;
        field[j * gw + i] = ((Math.sin(wx * 1.7 + t * 6) + Math.sin(wy * 2.1 - t * 4.7) + Math.sin((wx + wy) * 1.2 + t * 3.1)) / 6 + .5) * (LEVELS - .001);
      }
    }
    let o = 0;
    for (let y = 0; y < bh; y++) {                    // blend up to every dot, then dither
      const gy = Math.floor(y / K), fy = (y % K) / K, r0 = gy * gw, r1 = r0 + gw, trow = (y & 3) * 4;
      for (let x = 0; x < bw; x++) {
        const gx = colIdx[x], fx = colFrac[x];
        const top = field[r0 + gx] + (field[r0 + gx + 1] - field[r0 + gx]) * fx, bot = field[r1 + gx] + (field[r1 + gx + 1] - field[r1 + gx]) * fx;
        let level = (top + (bot - top) * fy + thr[trow + (x & 3)]) | 0;
        if (level < 0) level = 0; else if (level >= LEVELS) level = LEVELS - 1;
        px32[o++] = pal[level];
      }
    }
    bctx.putImageData(img, 0, 0);
  }
  const loop = now => {
    if (!running) return;
    if (now - last > interval) { last = now; paintBg(now); }
    requestAnimationFrame(loop);
  };
  const setRunning = () => {
    const on = !document.hidden && !window.jarvisMotionPaused && !reduced.matches;
    if (on && !running) { running = true; requestAnimationFrame(loop); } else if (!on) running = false;
  };

  // ---------------- pixel trail ----------------
  const PIX = 8, RADIUS = 78, DECAY = .045;
  let cols = 0, rows = 0, cells = new Float32Array(0), phase = new Float32Array(0), mx = -1e4, my = -1e4, trailBusy = false;
  const sizeTrail = () => {
    const dpr = Math.min(2, devicePixelRatio || 1), w = innerWidth, h = innerHeight;
    trail.width = Math.round(w * dpr); trail.height = Math.round(h * dpr);
    tctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cols = Math.ceil(w / PIX); rows = Math.ceil(h / PIX);
    cells = new Float32Array(cols * rows); phase = new Float32Array(cols * rows);
    for (let i = 0; i < phase.length; i++) phase[i] = Math.random();
  };
  // colours are looked up from a small table (8 hue positions x 16 strengths), rebuilt when the theme changes: no string building per dot per frame
  let trailTable = [];
  const buildTrailTable = () => {
    const n = trailColors.length - 1, aMax = dark ? .55 : .5;
    trailTable = [];
    for (let h = 0; h < 8; h++) { const row = []; for (let q = 0; q < 16; q++) {
      const inten = (q + 1) / 16, u = ((h / 8 * .5 + (1 - inten) * .5) % 1) * n, i = Math.min(n - 1, Math.floor(u)), f = u - i, c0 = trailColors[i], c1 = trailColors[i + 1];
      row.push('rgba(' + Math.round(c0[0] + (c1[0] - c0[0]) * f) + ',' + Math.round(c0[1] + (c1[1] - c0[1]) * f) + ',' + Math.round(c0[2] + (c1[2] - c0[2]) * f) + ',' + (inten * aMax).toFixed(3) + ')');
    } trailTable.push(row); }
  };
  let lit = { x0: 0, x1: -1, y0: 0, y1: -1 };            // cells that were lit last frame (only this area is scanned)
  const trailFrame = () => {
    if (document.hidden || window.jarvisMotionPaused) { trailBusy = false; return; }
    tctx.clearRect(0, 0, innerWidth, innerHeight);
    const x0 = Math.max(0, Math.floor((mx - RADIUS) / PIX)), x1 = Math.min(cols - 1, Math.ceil((mx + RADIUS) / PIX));
    const y0 = Math.max(0, Math.floor((my - RADIUS) / PIX)), y1 = Math.min(rows - 1, Math.ceil((my + RADIUS) / PIX));
    for (let j = y0; j <= y1; j++) for (let i = x0; i <= x1; i++) {      // light up the cells near the mouse
      const dist = Math.hypot(i * PIX + PIX / 2 - mx, j * PIX + PIX / 2 - my);
      if (dist < RADIUS) { const target = Math.pow(1 - dist / RADIUS, 1.5), k = j * cols + i; if (target > cells[k]) cells[k] += (target - cells[k]) * .35; }
    }
    const sx0 = Math.min(lit.x0, x0), sx1 = Math.max(lit.x1, x1), sy0 = Math.min(lit.y0, y0), sy1 = Math.max(lit.y1, y1);
    let nx0 = 1e9, nx1 = -1, ny0 = 1e9, ny1 = -1, any = false;
    for (let j = Math.max(0, sy0); j <= Math.min(rows - 1, sy1); j++) for (let i = Math.max(0, sx0); i <= Math.min(cols - 1, sx1); i++) {   // everything fades slowly: that is the trail
      const k = j * cols + i, v = cells[k];
      if (v < .012) { cells[k] = 0; continue; }
      cells[k] = v * (1 - DECAY); any = true;
      if (i < nx0) nx0 = i; if (i > nx1) nx1 = i; if (j < ny0) ny0 = j; if (j > ny1) ny1 = j;
      tctx.fillStyle = trailTable[(phase[k] * 8) | 0][Math.min(15, (v * 16) | 0)];
      tctx.fillRect(i * PIX, j * PIX, PIX - 1, PIX - 1);
    }
    lit = { x0: nx0, x1: nx1, y0: ny0, y1: ny1 };
    if (any) requestAnimationFrame(trailFrame); else trailBusy = false;
  };
  const wakeTrail = () => { if (!trailBusy) { trailBusy = true; requestAnimationFrame(trailFrame); } };
  addEventListener('pointermove', e => {
    if (e.pointerType !== 'mouse' || !fine.matches || reduced.matches) return;
    mx = e.clientX; my = e.clientY;
    wakeTrail();
  }, { passive: true });
  document.documentElement.addEventListener('mouseleave', () => { mx = my = -1e4; });

  // ---------------- wiring ----------------
  let rt = 0;
  addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { sizeBg(); sizeTrail(); setPalette(); paintBg(performance.now()); }, 150); }, { passive: true });
  document.addEventListener('visibilitychange', setRunning);
  addEventListener('jarvismotionchange', setRunning);
  reduced.addEventListener?.('change', setRunning);
  new MutationObserver(readTheme).observe(root, { attributes: true, attributeFilter: ['data-theme'] });
  sizeBg(); sizeTrail(); readTheme(); setRunning();
})();
