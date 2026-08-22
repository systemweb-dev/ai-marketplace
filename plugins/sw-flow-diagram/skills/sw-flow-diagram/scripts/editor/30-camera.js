/* ---- câmera: zoom, pan, enquadrar ---- */
const CONTENT = (svg.getAttribute('data-vb') || '0 0 1200 800').split(' ').map(Number);
const cam = { x: 0, y: 0, k: 1 };
const ZOOM_MIN = 0.15, ZOOM_MAX = 4;

function applyCam() {
  const w = stage.clientWidth || CONTENT[2], hh = stage.clientHeight || CONTENT[3];
  svg.setAttribute('width', w);
  svg.setAttribute('height', hh);
  svg.setAttribute('viewBox', `${cam.x} ${cam.y} ${w / cam.k} ${hh / cam.k}`);
  onCameraMove();
}
/** Retângulo que envolve TUDO que está desenhado — não o data-vb do build, que fica
    desatualizado assim que alguém move ou adiciona um nó. */
function contentBBox() {
  const ids = Object.keys(POS);
  if (!ids.length) return [CONTENT[0], CONTENT[1], CONTENT[0] + CONTENT[2], CONTENT[1] + CONTENT[3]];
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  ids.forEach(id => {
    const p = POS[id];
    x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]);
    x1 = Math.max(x1, p[0] + NW); y1 = Math.max(y1, p[1] + NH);
  });
  return [x0 - 30, y0 - 46, x1 + 30, y1 + 30];      // folga extra em cima: rótulo do grupo
}
function fitView(animate) {
  const b = contentBBox();
  const w = stage.clientWidth || CONTENT[2], hh = stage.clientHeight || CONTENT[3];
  const pad = 40, cw = b[2] - b[0], ch = b[3] - b[1];
  const k = clamp(Math.min((w - 2 * pad) / cw, (hh - 2 * pad) / ch), ZOOM_MIN, 1.6);
  const nx = b[0] + cw / 2 - (w / k) / 2, ny = b[1] + ch / 2 - (hh / k) / 2;
  if (animate) glideTo(nx, ny, k); else { cam.x = nx; cam.y = ny; cam.k = k; applyCam(); }
}
/** Movimento suave da câmera — usado pelo modo apresentação, onde um salto seco
    faz a plateia perder a referência de onde estava. */
let glideRAF = null;
function glideTo(x, y, k, ms) {
  cancelAnimationFrame(glideRAF);
  const from = { ...cam }, t0 = performance.now(), dur = ms || 380;
  const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  (function step(now) {
    const t = Math.min(1, (now - t0) / dur), e = ease(t);
    cam.x = from.x + (x - from.x) * e;
    cam.y = from.y + (y - from.y) * e;
    cam.k = from.k + (k - from.k) * e;
    applyCam();
    if (t < 1) glideRAF = requestAnimationFrame(step);
  })(t0);
}
/** Enquadra um conjunto de nós (apresentação passo-a-passo). */
function focusNodes(ids, zoomMax) {
  const pts = ids.map(id => POS[id]).filter(Boolean);
  if (!pts.length) return;
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  pts.forEach(p => {
    x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]);
    x1 = Math.max(x1, p[0] + NW); y1 = Math.max(y1, p[1] + NH);
  });
  const pad = 120, w = stage.clientWidth, hh = stage.clientHeight;
  const k = clamp(Math.min((w - 2 * pad) / (x1 - x0), (hh - 2 * pad) / (y1 - y0)), ZOOM_MIN, zoomMax || 1.25);
  glideTo((x0 + x1) / 2 - (w / k) / 2, (y0 + y1) / 2 - (hh / k) / 2, k);
}
function zoomBy(factor, cx, cy) {
  const r = svg.getBoundingClientRect();
  const px = cx == null ? r.width / 2 : cx - r.left, py = cy == null ? r.height / 2 : cy - r.top;
  const mx = cam.x + px / cam.k, my = cam.y + py / cam.k;
  cam.k = clamp(cam.k * factor, ZOOM_MIN, ZOOM_MAX);
  cam.x = mx - px / cam.k; cam.y = my - py / cam.k;
  applyCam();
}
