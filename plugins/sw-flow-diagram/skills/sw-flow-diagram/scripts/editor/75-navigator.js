/* ---- navegação de diagramas grandes ---- */
function shortestDirectedPath(from, to) {
  if (!from || !to) return [];
  const next = {};
  (F.edges || []).forEach(e => { (next[e.from] ||= []).push(e.to); });
  Object.values(next).forEach(list => list.sort());
  const queue = [from], previous = { [from]: null };
  while (queue.length) {
    const id = queue.shift();
    if (id === to) break;
    (next[id] || []).forEach(child => { if (!(child in previous)) { previous[child] = id; queue.push(child); } });
  }
  if (!(to in previous)) return [];
  const path = []; for (let id = to; id !== null; id = previous[id]) path.unshift(id);
  return path;
}

function openNavigator() {
  document.querySelectorAll('.navigator').forEach(el => el.remove());
  const box = document.createElement('aside'); box.className = 'navigator';
  box.innerHTML = '<strong>Navegação</strong><input aria-label="Filtrar nós" placeholder="Filtrar nós…"><svg class="navmini" aria-label="Minimap"></svg><div class="navpath"><select aria-label="Origem"></select><select aria-label="Destino"></select><button>Focar caminho</button></div><div class="navlist"></div>';
  document.body.appendChild(box);
  const input = box.querySelector('input'), list = box.querySelector('.navlist'), from = box.querySelectorAll('select')[0], to = box.querySelectorAll('select')[1];
  const nodes = () => (F.nodes || []).slice().sort((a, b) => (a.label || a.id).localeCompare(b.label || b.id));
  nodes().forEach(n => { [from, to].forEach(select => { const opt = document.createElement('option'); opt.value = n.id; opt.textContent = n.label || n.id; select.appendChild(opt); }); });
  function drawMini() {
    const mini = box.querySelector('.navmini'), points = Object.values(POS);
    if (!points.length) return;
    const maxX = Math.max(...points.map(p => p[0] + NW)) + 40, maxY = Math.max(...points.map(p => p[1] + NH)) + 40;
    mini.setAttribute('viewBox', `0 0 ${maxX} ${maxY}`); mini.innerHTML = '';
    (F.nodes || []).forEach(n => { const p = POS[n.id]; if (!p) return; const r = document.createElementNS('http://www.w3.org/2000/svg', 'rect'); r.setAttribute('x', p[0]); r.setAttribute('y', p[1]); r.setAttribute('width', NW); r.setAttribute('height', NH); r.setAttribute('rx', 8); r.setAttribute('class', sel.nodes.has(n.id) ? 'on' : ''); r.onclick = () => { clearSel(); selectNode(n.id); focusNodes([n.id], 1.1); render(); }; mini.appendChild(r); });
  }
  function draw() {
    list.innerHTML = '';
    nodes().filter(n => !input.value || (n.label || n.id).toLowerCase().includes(input.value.toLowerCase())).forEach(n => {
      const b = document.createElement('button'); b.textContent = n.label || n.id; b.onclick = () => { clearSel(); selectNode(n.id); focusNodes([n.id], 1.1); render(); }; list.appendChild(b);
    });
    drawMini();
  }
  input.oninput = draw;
  box.querySelector('button').onclick = () => { const path = shortestDirectedPath(from.value, to.value); if (!path.length) return alert('Não há caminho dirigido entre estes nós.'); clearSel(); path.forEach(id => sel.nodes.add(id)); focusNodes(path, 1.05); render(); };
  draw(); input.focus();
}

if (typeof document !== 'undefined') {
  const style = document.createElement('style'); style.textContent = '.navigator{position:fixed;z-index:80;right:14px;top:58px;width:270px;max-height:calc(100vh - 76px);overflow:auto;padding:12px;border:1px solid var(--line);border-radius:12px;background:var(--card,var(--bg));box-shadow:0 14px 32px #0002;color:var(--ink);font:12px var(--display)}.navigator strong{display:block;margin-bottom:8px}.navigator input,.navigator select,.navigator button{box-sizing:border-box;width:100%;margin:3px 0;padding:7px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--ink)}.navmini{width:100%;height:110px;margin:8px 0;border:1px solid var(--line);background:var(--bg)}.navmini rect{fill:var(--muted);opacity:.5;cursor:pointer}.navmini rect.on{fill:var(--accent);opacity:1}.navpath{display:grid;grid-template-columns:1fr 1fr;gap:3px}.navpath button{grid-column:1/-1;background:var(--accent);color:white}.navlist button{text-align:left;cursor:pointer}'; document.head.appendChild(style);
}
if (typeof module === 'object' && module.exports) module.exports = { shortestDirectedPath };

function addNavigatorButton() {
  const bar = document.querySelector('.bar'), anchor = bar && bar.querySelector('.sp');
  if (!anchor || document.getElementById('navBtn')) return;
  const b = document.createElement('button'); b.id = 'navBtn'; b.className = 'btn'; b.textContent = 'Navegar'; b.title = 'Abrir navegação'; b.setAttribute('aria-label', b.title); b.onclick = openNavigator;
  bar.insertBefore(b, anchor);
}
if (typeof document !== 'undefined') addNavigatorButton();
