/* ---- organização determinística da seleção e do fluxo ---- */
function selectedPoints(ids) {
  return ids.map(id => POS[id]).filter(Boolean);
}

function alignNodes(ids, axis, edge) {
  const points = selectedPoints(ids);
  if (points.length < 2) return false;
  const value = edge === 'min' ? Math.min(...points.map(p => p[axis])) : Math.max(...points.map(p => p[axis]));
  ids.forEach(id => { if (POS[id]) POS[id][axis] = value; });
  return true;
}

function distributeNodes(ids, axis) {
  const ordered = ids.filter(id => POS[id]).sort((a, b) => POS[a][axis] - POS[b][axis] || a.localeCompare(b));
  if (ordered.length < 3) return false;
  const first = POS[ordered[0]][axis], last = POS[ordered.at(-1)][axis];
  const gap = (last - first) / (ordered.length - 1);
  ordered.forEach((id, i) => { POS[id][axis] = first + gap * i; });
  return true;
}

function autoLayoutModel() {
  const nodes = F.nodes || [], edges = F.edges || [];
  const ids = nodes.map(n => n.id).sort();
  const indegree = Object.fromEntries(ids.map(id => [id, 0]));
  const next = Object.fromEntries(ids.map(id => [id, []]));
  edges.forEach(e => { if (next[e.from] && next[e.to]) { next[e.from].push(e.to); indegree[e.to] += 1; } });
  const layers = [], remaining = new Set(ids);
  while (remaining.size) {
    const layer = ids.filter(id => remaining.has(id) && indegree[id] === 0);
    const chosen = layer.length ? layer : [Array.from(remaining).sort()[0]];
    chosen.forEach(id => { remaining.delete(id); next[id].forEach(to => { indegree[to] -= 1; }); });
    layers.push(chosen);
  }
  layers.forEach((layer, x) => layer.forEach((id, y) => {
    POS[id] = [60 + x * (NW + 88), 60 + y * (NH + 34)];
  }));
  return layers;
}

function addLayoutControls() {
  const bar = document.querySelector('.bar');
  const anchor = bar && bar.querySelector('.sp');
  if (!anchor || document.getElementById('layoutTools')) return;
  const tools = document.createElement('div');
  tools.id = 'layoutTools'; tools.className = 'grp';
  const button = (id, label, title, fn) => {
    const el = document.createElement('button'); el.className = 'btn'; el.id = id; el.textContent = label; el.title = title;
    el.setAttribute('aria-label', title); el.onclick = fn; tools.appendChild(el);
  };
  button('arrangeBtn', 'Organizar', 'Organizar o diagrama', () => { beginChange(); autoLayoutModel(); render(); });
  button('alignBtn', 'Alinhar', 'Alinhar seleção pela esquerda', () => { if (sel.nodes.size > 1) { beginChange(); alignNodes(selNodeIds(), 0, 'min'); render(); } });
  button('distributeBtn', 'Distribuir', 'Distribuir seleção horizontalmente', () => { if (sel.nodes.size > 2) { beginChange(); distributeNodes(selNodeIds(), 0); render(); } });
  bar.insertBefore(tools, anchor);
}

if (typeof document !== 'undefined') addLayoutControls();
if (typeof module === 'object' && module.exports) module.exports = { alignNodes, distributeNodes, autoLayoutModel };
