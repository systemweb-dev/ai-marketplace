/* ---- interação: arrastar (com guias), laço, conectar, religar, teclado ---- */
const SNAP = 6;                        // tolerância de encaixe, em unidades do diagrama

/** Guias de alinhamento: compara o nó arrastado com os demais e devolve o
    deslocamento que encaixa, mais as linhas a desenhar. É o detalhe que faz o
    diagrama sair alinhado sem ninguém medir nada. */
function alignmentGuides(movingIds, x, y) {
  const moving = new Set(movingIds);
  const alvos = [];
  (F.nodes || []).forEach(n => {
    if (moving.has(n.id) || !POS[n.id] || !nodeVisible(n)) return;
    const p = POS[n.id];
    alvos.push({ cx: p[0] + NW / 2, cy: p[1] + NH / 2, x0: p[0], y0: p[1], x1: p[0] + NW, y1: p[1] + NH });
  });
  const meu = { cx: x + NW / 2, cy: y + NH / 2, x0: x, y0: y, x1: x + NW, y1: y + NH };
  let dx = 0, dy = 0; const linhas = [];
  let melhorX = SNAP + 1, melhorY = SNAP + 1;
  alvos.forEach(a => {
    [['cx', 'cx'], ['x0', 'x0'], ['x1', 'x1'], ['x0', 'x1'], ['x1', 'x0']].forEach(([m, o]) => {
      const d = a[o] - meu[m];
      if (Math.abs(d) < Math.abs(melhorX)) { melhorX = d; }
    });
    [['cy', 'cy'], ['y0', 'y0'], ['y1', 'y1'], ['y0', 'y1'], ['y1', 'y0']].forEach(([m, o]) => {
      const d = a[o] - meu[m];
      if (Math.abs(d) < Math.abs(melhorY)) { melhorY = d; }
    });
  });
  if (Math.abs(melhorX) <= SNAP) { dx = melhorX; linhas.push(['v', meu.cx + dx]); }
  if (Math.abs(melhorY) <= SNAP) { dy = melhorY; linhas.push(['h', meu.cy + dy]); }
  return { dx, dy, linhas };
}
function drawGuides(linhas) {
  svg.querySelectorAll('.guide').forEach(e => e.remove());
  const b = contentBBox();
  linhas.forEach(([dir, v]) => {
    const at = dir === 'v' ? { x1: v, y1: b[1] - 400, x2: v, y2: b[3] + 400 }
                           : { x1: b[0] - 400, y1: v, x2: b[2] + 400, y2: v };
    svg.appendChild(mk('line', { ...at, class: 'guide' }));
  });
}

/** Reflete a seleção no DOM sem re-renderizar.

    Um render() aqui destruiria o próprio elemento que recebeu o pointerdown — junto com
    o pointer capture e os listeners do arrasto. Era exatamente por isso que arrastar
    parava de funcionar assim que o nó ficava selecionado. */
function pintarSelecao() {
  svg.querySelectorAll('.node').forEach(el => {
    el.classList.toggle('sel', isNodeSelected(el.getAttribute('data-id')));
  });
  svg.querySelectorAll('.edge').forEach(el => {
    el.classList.toggle('sel', sel.edge === +el.getAttribute('data-i'));
  });
  renderPanel();
}

function bindNode(g, n) {
  g.querySelectorAll('.port').forEach(port => {
    port.addEventListener('pointerdown', ev => {
      ev.stopPropagation();
      startConnect(ev, n.id, port.getAttribute('data-side'));
    });
  });
  g.addEventListener('dblclick', ev => { ev.stopPropagation(); editLabel('n', n.id); });
  g.addEventListener('pointerdown', ev => {
    if (ev.button !== 0 || ev.target.classList.contains('port')) return;
    ev.preventDefault();
    const additive = ev.shiftKey || ev.ctrlKey || ev.metaKey;
    if (!isNodeSelected(n.id)) selectNode(n.id, additive);
    else if (additive) { selectNode(n.id, true); pintarSelecao(); return; }
    pintarSelecao();

    const ids = selNodeIds();
    const inicio = toSvg(ev);
    const base = {}; ids.forEach(id => { if (POS[id]) base[id] = [...POS[id]]; });
    let mexeu = false, registrou = false;
    document.body.classList.add('dragging');

    const mv = e => {
      const q = toSvg(e);
      let dx = q.x - inicio.x, dy = q.y - inicio.y;
      if (!mexeu && Math.abs(dx) + Math.abs(dy) < 3) return;
      if (!registrou) { beginChange(); registrou = true; }   // só grava histórico se moveu de fato
      mexeu = true;
      if (base[n.id]) {
        const gd = alignmentGuides(ids, base[n.id][0] + dx, base[n.id][1] + dy);
        dx += gd.dx; dy += gd.dy;
        drawGuides(gd.linhas);
      }
      ids.forEach(id => { if (base[id]) POS[id] = [Math.max(0, base[id][0] + dx), Math.max(0, base[id][1] + dy)]; });
      quickRedraw(ids);
    };
    const up = () => {
      // na janela, não no nó: durante o arrasto o ponteiro sai de cima da caixa a toda hora
      window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up);
      document.body.classList.remove('dragging');
      svg.querySelectorAll('.guide').forEach(e => e.remove());
      render();
    };
    window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up);
  });
}

/** Redesenho barato durante o arrasto: move só os nós afetados e reroteia as arestas.
    Um render() completo a cada pointermove trava em diagrama grande. */
function quickRedraw(ids) {
  ids.forEach(id => {
    const el = svg.querySelector(`.node[data-id="${id}"]`);
    if (el && POS[id]) el.setAttribute('transform', `translate(${POS[id][0].toFixed(1)},${POS[id][1].toFixed(1)})`);
  });
  const set = new Set(ids);
  svg.querySelectorAll('.edge').forEach(p => {
    const ed = F.edges[+p.getAttribute('data-i')];
    if (!ed || (!set.has(ed.from) && !set.has(ed.to))) return;
    const geo = edgeGeom(ed);
    if (geo) p.setAttribute('d', geo.d);
  });
  svg.querySelectorAll('.group,.gcollapsed').forEach(e => e.remove());
  const antes = svg.querySelector('.edge') || svg.querySelector('.node');
  const tmp = document.createDocumentFragment();
  const alvo = svg;
  renderGroupsInto(tmp);
  if (antes) alvo.insertBefore(tmp, antes); else alvo.appendChild(tmp);
  onRender();
}
function renderGroupsInto(frag) {
  const guarda = svg.appendChild.bind(svg);
  svg.appendChild = el => frag.appendChild(el);
  try { renderGroups(); } finally { svg.appendChild = guarda; }
}

let ghost = null;
function startConnect(ev, fromId, lado) {
  ghost = mk('path', { class: 'edge ghost', d: '' });
  svg.appendChild(ghost);
  document.body.classList.add('dragging');
  document.body.classList.add('connecting');       // acende as portas de todos os nós
  const box = endBox(endpointOf(fromId));
  const p1 = anchorSide(box.pos, lado || 'right', box.w, box.h);
  let ladoAlvo = null;
  const mv = e => {
    const l = toSvg(e);
    const sob = nodeUnder(e);
    // enquanto está sobre um nó, mostra em qual lado vai encostar
    ladoAlvo = sob && POS[sob] ? ladoMaisProximo(POS[sob], l) : null;
    const p2 = ladoAlvo ? anchorSide(POS[sob], ladoAlvo, NW, NH) : [l.x, l.y];
    ghost.setAttribute('d', edgePath(p1[0], p1[1], p2[0], p2[1], lado || 'right', ladoAlvo || 'left'));
  };
  const up = e => {
    window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up);
    document.body.classList.remove('dragging', 'connecting');
    ghost.remove(); ghost = null;
    const alvo = nodeUnder(e);
    if (alvo && alvo !== fromId) {
      beginChange();
      if (addEdge(fromId, alvo)) {
        const nova = F.edges[F.edges.length - 1];
        if (lado) nova.fromSide = lado;
        if (ladoAlvo) nova.toSide = ladoAlvo;
      }
    }
    render();
  };
  window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up);
}
/** Lado da caixa mais próximo do ponto — decide onde a seta encosta ao soltar. */
function ladoMaisProximo(pos, pt) {
  let melhor = 'left', dist = Infinity;
  SIDES.forEach(s => {
    const a = anchorSide(pos, s, NW, NH);
    const d = (a[0] - pt.x) ** 2 + (a[1] - pt.y) ** 2;
    if (d < dist) { dist = d; melhor = s; }
  });
  return melhor;
}
function startRelink(ev, idx, end) {
  ev.stopPropagation();
  const ed = F.edges[idx];
  document.body.classList.add('dragging');
  let ladoNovo = null;
  const mv = e => {
    const l = toSvg(e);
    const geo = edgeGeom(ed);
    if (!geo) return;
    const sob = nodeUnder(e);
    ladoNovo = sob && POS[sob] ? ladoMaisProximo(POS[sob], l) : null;
    const movel = ladoNovo && sob ? anchorSide(POS[sob], ladoNovo, NW, NH) : [l.x, l.y];
    const fixo = end === 'from' ? geo.p2 : geo.p1;
    const p = svg.querySelector(`.edge[data-i="${idx}"]`);
    if (!p) return;
    p.setAttribute('d', end === 'from'
      ? edgePath(movel[0], movel[1], fixo[0], fixo[1], ladoNovo || 'right', geo.s2)
      : edgePath(fixo[0], fixo[1], movel[0], movel[1], geo.s1, ladoNovo || 'left'));
  };
  const up = e => {
    window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up);
    document.body.classList.remove('dragging');
    const alvo = nodeUnder(e);
    const outro = ed[end === 'from' ? 'to' : 'from'];
    if (alvo && alvo !== outro) {
      beginChange();
      ed[end] = alvo;
      if (ladoNovo) ed[end === 'from' ? 'fromSide' : 'toSide'] = ladoNovo;
    }
    render();
  };
  window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up);
}
function nodeUnder(e) {
  const el = document.elementFromPoint(e.clientX, e.clientY);
  const g = el && el.closest && el.closest('.node');
  return g ? g.getAttribute('data-id') : null;
}

/** Laço de seleção: arrastar no fundo com Shift, ou com a ferramenta de seleção ativa. */
function startMarquee(ev) {
  const a = toSvg(ev);
  const r = mk('rect', { class: 'marquee', x: a.x, y: a.y, width: 0, height: 0 });
  svg.appendChild(r);
  const mv = e => {
    const b = toSvg(e);
    r.setAttribute('x', Math.min(a.x, b.x)); r.setAttribute('y', Math.min(a.y, b.y));
    r.setAttribute('width', Math.abs(b.x - a.x)); r.setAttribute('height', Math.abs(b.y - a.y));
  };
  const up = e => {
    window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up);
    const b = toSvg(e);
    const x0 = Math.min(a.x, b.x), x1 = Math.max(a.x, b.x), y0 = Math.min(a.y, b.y), y1 = Math.max(a.y, b.y);
    r.remove();
    if (!(ev.shiftKey && (x1 - x0) < 4)) clearSel();
    (F.nodes || []).forEach(n => {
      const p = POS[n.id];
      if (!p || !nodeVisible(n)) return;
      if (p[0] + NW > x0 && p[0] < x1 && p[1] + NH > y0 && p[1] < y1) sel.nodes.add(n.id);
    });
    render();
  };
  window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up);
}
