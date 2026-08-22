/* ---- modelo + histórico (desfazer/refazer) ----
   Toda mutação do diagrama passa por `commit()`. É o que torna Ctrl+Z confiável:
   em vez de tentar inverter cada operação (fonte infinita de bug), guardamos o
   estado inteiro antes de mudar. Um diagrama é pequeno o bastante pra isso ser barato. */

const GROUP_COLORS = ['#e8743b', '#2f6bf0', '#37a86b', '#8b5cf6', '#e0407f', '#0ea5b7', '#d9a406'];
const HISTORY_MAX = 60;

const past = [], future = [];
let dirty = false;

function snapshot() {
  return JSON.stringify({ nodes: F.nodes || [], edges: F.edges || [], groups: F.groups || [], pos: POS });
}
function restore(snap) {
  const s = JSON.parse(snap);
  F.nodes = s.nodes; F.edges = s.edges; F.groups = s.groups;
  for (const k in POS) delete POS[k];
  for (const k in s.pos) POS[k] = s.pos[k];
}

/** Registra o estado ANTES de uma mudança. Chame no início de toda mutação. */
function beginChange() {
  past.push(snapshot());
  if (past.length > HISTORY_MAX) past.shift();
  future.length = 0;
  dirty = true;
}
function undo() {
  if (!past.length) return false;
  future.push(snapshot());
  restore(past.pop());
  return true;
}
function redo() {
  if (!future.length) return false;
  past.push(snapshot());
  restore(future.pop());
  return true;
}
const canUndo = () => past.length > 0;
const canRedo = () => future.length > 0;

// ---- consultas
const nodeById = id => (F.nodes || []).find(n => n.id === id);
const groupById = id => (F.groups || []).find(g => g.id === id);
const nodesOfGroup = gid => (F.nodes || []).filter(n => n.group === gid);
const edgeEnds = ed => {
  const a = POS[ed.from], b = POS[ed.to];
  if (!a || !b) return null;
  const o = anchorOut(a), i = anchorIn(b);
  return [o[0], o[1], i[0], i[1]];
};
/** Retângulo que envolve os nós de um grupo (null se o grupo está vazio/recolhido). */
function groupBBox(gid) {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9, has = false;
  (F.nodes || []).forEach(n => {
    if (n.group !== gid || !POS[n.id]) return;
    has = true; const p = POS[n.id];
    x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]);
    x1 = Math.max(x1, p[0] + NW); y1 = Math.max(y1, p[1] + NH);
  });
  return has ? [x0, y0, x1, y1] : null;
}

// ---- mutações
function addNode(pt, label, icon, group) {
  const id = newId();
  const n = { id, label: label || 'Novo', icon: icon || 'box' };
  if (group) n.group = group;
  F.nodes.push(n);
  POS[id] = [pt[0] - NW / 2, pt[1] - NH / 2];
  return id;
}
function removeNodes(ids) {
  const set = new Set(ids);
  F.nodes = (F.nodes || []).filter(n => !set.has(n.id));
  F.edges = (F.edges || []).filter(e => !set.has(e.from) && !set.has(e.to));
  ids.forEach(id => delete POS[id]);
}
function addEdge(from, to) {
  if (from === to) return false;
  F.edges = F.edges || [];
  if (F.edges.some(e => e.from === from && e.to === to)) return false;  // não duplica
  F.edges.push({ from, to, animated: true });
  return true;
}
/** Copia nós e as arestas INTERNAS à seleção, deslocados. Arestas para fora não são
    duplicadas: o clone apontaria pro mesmo destino e viraria ruído no diagrama. */
function duplicateNodes(ids, dx, dy) {
  const map = {}, novos = [];
  ids.forEach(id => {
    const n = nodeById(id); if (!n || !POS[id]) return;
    const clone = JSON.parse(JSON.stringify(n));
    clone.id = newId(); map[id] = clone.id;
    F.nodes.push(clone);
    POS[clone.id] = [POS[id][0] + dx, POS[id][1] + dy];
    novos.push(clone.id);
  });
  (F.edges || []).slice().forEach(e => {
    if (map[e.from] && map[e.to]) F.edges.push({ ...e, from: map[e.from], to: map[e.to] });
  });
  return novos;
}
function ensureGroup(name) {
  const existentes = new Set((F.groups || []).map(g => g.id));
  let id = slug(name), u = id, i = 2;
  while (existentes.has(u)) u = id + '-' + (i++);
  F.groups = F.groups || [];
  F.groups.push({ id: u, label: name, color: GROUP_COLORS[F.groups.length % GROUP_COLORS.length] });
  return u;
}
