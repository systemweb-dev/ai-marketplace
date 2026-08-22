/* ---- util: DOM/SVG, geometria e ids. Sem estado. ---- */
const NS = 'http://www.w3.org/2000/svg';
const svg = document.getElementById('dg');
const stage = svg.parentElement;

const F = window.FLOW, POS = window.POS, ICN = window.ICON_SVG;
const NW = window.NW, NH = window.NH, CAT = window.CATALOG || [];
const ANIM = window.ANIM, DUR = window.DUR;
const VERT = (F.direction || 'LR').toUpperCase() === 'TB' && F.layout !== 'tiers';

/** Cria elemento SVG com atributos. `inner` entra como innerHTML (usado só p/ ícones nossos). */
function mk(tag, attrs, inner) {
  const el = document.createElementNS(NS, tag);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  if (inner != null) el.innerHTML = inner;
  return el;
}
/** Cria elemento HTML com classe e conteúdo opcionais. */
function h(tag, cls, inner) {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (inner != null) el.innerHTML = inner;
  return el;
}
/** Ponto do evento convertido para coordenadas do SVG (respeita zoom/pan). */
function toSvg(e) {
  const p = svg.createSVGPoint();
  p.x = e.clientX; p.y = e.clientY;
  return p.matrixTransform(svg.getScreenCTM().inverse());
}
/** Ponto do SVG convertido para coordenadas de tela (posicionar UI HTML sobre o canvas). */
function toScreen(x, y) {
  const p = svg.createSVGPoint();
  p.x = x; p.y = y;
  return p.matrixTransform(svg.getScreenCTM());
}

// Os quatro lados de conexão. Guardar o lado (e não só "entrada/saída") é o que permite
// ligar por cima/baixo: a curva sai perpendicular à borda, como em Miro/Whimsical.
const SIDES = ['right', 'bottom', 'left', 'top'];
const SIDE_VEC = { right: [1, 0], left: [-1, 0], bottom: [0, 1], top: [0, -1] };

/** Ponto de um lado de uma caixa em (p) com tamanho w×hh. */
function anchorSide(p, side, w, hh) {
  w = w || NW; hh = hh || NH;
  switch (side) {
    case 'left':   return [p[0], p[1] + hh / 2];
    case 'top':    return [p[0] + w / 2, p[1]];
    case 'bottom': return [p[0] + w / 2, p[1] + hh];
    default:       return [p[0] + w, p[1] + hh / 2];
  }
}
/** Lado padrão quando a aresta não guarda um: escolhe pelo eixo dominante entre os centros. */
function autoSides(a, b, wa, ha, wb, hb) {
  const ca = [a[0] + (wa || NW) / 2, a[1] + (ha || NH) / 2];
  const cb = [b[0] + (wb || NW) / 2, b[1] + (hb || NH) / 2];
  const dx = cb[0] - ca[0], dy = cb[1] - ca[1];
  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx >= 0 ? ['right', 'left'] : ['left', 'right'];
  }
  return dy >= 0 ? ['bottom', 'top'] : ['top', 'bottom'];
}
/** Bézier que sai perpendicular a cada lado — funciona pra qualquer combinação. */
function edgePath(x1, y1, x2, y2, s1, s2) {
  const v1 = SIDE_VEC[s1] || SIDE_VEC.right, v2 = SIDE_VEC[s2] || SIDE_VEC.left;
  const dist = Math.hypot(x2 - x1, y2 - y1);
  const d = clamp(dist * .42, 34, 130);
  return `M${x1},${y1} C${x1 + v1[0] * d},${y1 + v1[1] * d} ${x2 + v2[0] * d},${y2 + v2[1] * d} ${x2},${y2}`;
}
// mantidos p/ compatibilidade com o layout automático do build
const anchorOut = p => VERT ? anchorSide(p, 'bottom') : anchorSide(p, 'right');
const anchorIn  = p => VERT ? anchorSide(p, 'top')    : anchorSide(p, 'left');

let _uid = 0;
const newId = () => 'n' + Date.now().toString(36).slice(-4) + (_uid++);
const slug = s => (String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'g');
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
