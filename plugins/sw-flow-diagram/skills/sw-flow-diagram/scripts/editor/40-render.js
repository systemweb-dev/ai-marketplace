/* ---- render do modelo em SVG ---- */
const COLLAPSED = new Set();          // ids de grupos recolhidos
const CW = 210, CH = 74;              // caixa do grupo recolhido

const isCollapsed = gid => COLLAPSED.has(gid);
/** Nó visível? Não, se pertence a grupo recolhido. */
const nodeVisible = n => !(n.group && COLLAPSED.has(n.group));
/** Para onde uma aresta aponta de fato: se o nó está escondido, vale a caixa do grupo. */
const endpointOf = id => {
  const n = nodeById(id);
  return (n && n.group && COLLAPSED.has(n.group)) ? 'g:' + n.group : id;
};

/** Posição da caixa do grupo recolhido: centro de onde seus nós estavam. */
function collapsedPos(gid) {
  const ns = nodesOfGroup(gid).map(n => POS[n.id]).filter(Boolean);
  if (!ns.length) return [0, 0];
  const cx = ns.reduce((s, p) => s + p[0] + NW / 2, 0) / ns.length;
  const cy = ns.reduce((s, p) => s + p[1] + NH / 2, 0) / ns.length;
  return [cx - CW / 2, cy - CH / 2];
}
/** Caixa de uma extremidade: nó normal ou grupo recolhido. */
function endBox(key) {
  if (String(key).startsWith('g:')) {
    const p = collapsedPos(key.slice(2));
    return { pos: p, w: CW, h: CH };
  }
  const p = POS[key];
  return p ? { pos: p, w: NW, h: NH } : null;
}
/** Geometria completa de uma aresta: pontos e lados de saída/chegada. */
function edgeGeom(ed) {
  const A = endBox(endpointOf(ed.from)), B = endBox(endpointOf(ed.to));
  if (!A || !B) return null;
  const auto = autoSides(A.pos, B.pos, A.w, A.h, B.w, B.h);
  const s1 = ed.fromSide || auto[0], s2 = ed.toSide || auto[1];
  const p1 = anchorSide(A.pos, s1, A.w, A.h), p2 = anchorSide(B.pos, s2, B.w, B.h);
  return { p1, p2, s1, s2, d: edgePath(p1[0], p1[1], p2[0], p2[1], s1, s2) };
}
// compatibilidade com chamadas antigas
function endAnchors(key) {
  const b = endBox(key);
  return b ? { out: anchorSide(b.pos, VERT ? 'bottom' : 'right', b.w, b.h),
               in:  anchorSide(b.pos, VERT ? 'top' : 'left', b.w, b.h) } : null;
}

function render() {
  svg.querySelectorAll('.group,.lane,.edge,.elabel,.packet,.node,.ehandle,.gcollapsed').forEach(e => e.remove());
  renderGroups();
  renderEdges();
  (F.nodes || []).forEach((n, i) => { if (POS[n.id] && nodeVisible(n)) svg.appendChild(nodeNode(n, i)); });
  renderEdgeHandles();
  onRender();
}

function renderGroups() {
  (F.groups || []).forEach(gp => {
    const color = gp.color || '#8893a6';
    if (COLLAPSED.has(gp.id)) {
      const p = collapsedPos(gp.id), qtd = nodesOfGroup(gp.id).length;
      const g = mk('g', { class: 'gcollapsed', 'data-gid': gp.id, transform: `translate(${p[0]},${p[1]})` });
      g.appendChild(mk('rect', { x: 0, y: 0, width: CW, height: CH, rx: 14, class: 'cbox', style: '--gc:' + color }));
      const t = mk('text', { x: 16, y: 30, class: 'clabel' }); t.textContent = gp.label || gp.id;
      const s = mk('text', { x: 16, y: 52, class: 'csub' }); s.textContent = qtd + (qtd === 1 ? ' item' : ' itens') + ' · clique p/ abrir';
      g.appendChild(t); g.appendChild(s);
      g.appendChild(mk('text', { x: CW - 20, y: 34, class: 'cchev' }, '+'));
      g.addEventListener('pointerdown', ev => ev.stopPropagation());
      g.addEventListener('click', () => { COLLAPSED.delete(gp.id); render(); });
      svg.appendChild(g);
      return;
    }
    const b = groupBBox(gp.id); if (!b) return;
    const pad = 16, g = mk('g', { class: 'group', 'data-gid': gp.id });
    g.appendChild(mk('rect', { x: b[0] - pad, y: b[1] - pad - 14, width: b[2] - b[0] + 2 * pad,
                               height: b[3] - b[1] + 2 * pad + 14, rx: 16, class: 'gbox', style: '--gc:' + color }));
    const t = mk('text', { x: b[0] - pad + 6, y: b[1] - pad - 2, class: 'glabel', style: '--gc:' + color });
    t.textContent = gp.label || gp.id;
    g.appendChild(t);
    // botão de recolher, colado no rótulo
    const bx = b[0] - pad + 12 + (gp.label || gp.id).length * 6.4;
    const btn = mk('text', { x: bx, y: b[1] - pad - 2, class: 'gtoggle', style: '--gc:' + color }, '−');
    btn.addEventListener('pointerdown', ev => ev.stopPropagation());
    btn.addEventListener('click', ev => { ev.stopPropagation(); COLLAPSED.add(gp.id); clearSel(); render(); });
    g.appendChild(btn);
    svg.appendChild(g);
  });
}

function renderEdges() {
  const vistas = new Set();
  (F.edges || []).forEach((ed, i) => {
    const a = endpointOf(ed.from), b = endpointOf(ed.to);
    if (a === b) return;                            // aresta interna a um grupo recolhido
    const chave = a + '>' + b;
    if (vistas.has(chave)) return;                  // grupo recolhido funde paralelas
    vistas.add(chave);
    const geo = edgeGeom(ed);
    if (!geo) return;
    const c = [geo.p1[0], geo.p1[1], geo.p2[0], geo.p2[1]];
    const anim = ed.animated !== false;
    const cls = 'edge' + (anim ? ' animated' : '') + (ed.style === 'dashed' ? ' dashed' : '')
      + (sel.edge === i ? ' sel' : '') + (dimmed(a, b) ? ' dim' : '');
    const p = mk('path', { id: 'e' + i, 'data-i': i, d: geo.d, class: cls, 'marker-end': 'url(#arrow)' });
    p.style.pointerEvents = 'stroke';
    p.addEventListener('pointerdown', ev => { ev.stopPropagation(); selectEdge(i); render(); });
    p.addEventListener('dblclick', ev => { ev.stopPropagation(); editLabel('e', i); });
    svg.appendChild(p);
    if (ANIM === 'packet' && anim && !dimmed(a, b)) {
      // animateMotion SOMA uma translação sobre cx/cy — por isso o círculo fica em (0,0)
      // e quem o posiciona é o movimento. Só que, com `begin` escalonado, ele apareceria
      // parado no canto até a sua vez: nasce invisível e acende junto com o movimento.
      const atraso = (i * .25).toFixed(2) + 's';
      const pk = mk('circle', { r: 4.5, class: 'packet', opacity: 0 });
      const am = mk('animateMotion', { dur: DUR + 's', begin: atraso, repeatCount: 'indefinite' });
      am.appendChild(mk('mpath', { href: '#e' + i }));
      pk.appendChild(am);
      pk.appendChild(mk('set', { attributeName: 'opacity', to: 1, begin: atraso, fill: 'freeze' }));
      svg.appendChild(pk);
    }
    if (ed.label) {
      const t = mk('text', { x: ((c[0] + c[2]) / 2).toFixed(0), y: ((c[1] + c[3]) / 2 - 8).toFixed(0),
                             class: 'elabel' + (dimmed(a, b) ? ' dim' : '') });
      t.textContent = ed.label; svg.appendChild(t);
    }
  });
}

function renderEdgeHandles() {
  if (sel.edge === null || !F.edges[sel.edge]) return;
  const ed = F.edges[sel.edge];
  const geo = edgeGeom(ed);
  if (!geo) return;
  [['from', geo.p1], ['to', geo.p2]].forEach(([end, pt]) => {
    const el = mk('circle', { cx: pt[0], cy: pt[1], r: 7, class: 'ehandle', 'data-end': end });
    el.addEventListener('pointerdown', ev => startRelink(ev, sel.edge, end));
    svg.appendChild(el);
  });
}

/** Trunca o rótulo ao que cabe na forma. Sem isso, "Decisão de roteamento" transborda
    o losango e encosta na seta vizinha. ~6.6px por caractere no tamanho do rótulo. */
function ajustarTexto(txt, largura, centrado) {
  const max = Math.max(4, Math.floor(largura / 6.6));
  return txt.length <= max ? txt : txt.slice(0, max - 1).trimEnd() + '…';
}

function nodeNode(n, idx) {
  const at = {
    class: 'node' + (isNodeSelected(n.id) ? ' sel' : '') + (ANIM === 'highlight' ? ' hl' : '')
      + (dimmedNode(n.id) ? ' dim' : ''),
    'data-id': n.id, transform: `translate(${POS[n.id][0]},${POS[n.id][1]})`
  };
  if (ANIM === 'highlight') at.style = '--d:' + ((idx || 0) * .3).toFixed(2) + 's';
  if (n.note) at['data-note'] = n.note;
  const g = mk('g', at);
  const forma = n.shape || 'rounded';
  const geo = shapeGeom(forma, NW, NH);
  g.appendChild(mk(geo.tag, { ...geo.attrs, class: 'nbox' }));
  shapeExtras(forma, NW, NH).forEach(e => g.appendChild(mk(e.tag, e.attrs)));

  const gp = n.group && groupById(n.group);
  // a tarja de cor do grupo só faz sentido em forma retangular; nas demais ela cortaria o contorno
  if (gp && (forma === 'rounded' || forma === 'rect' || forma === 'subroutine'))
    g.appendChild(mk('rect', { x: 0, y: 0, width: 4, height: NH, rx: 2, class: 'nstripe',
                               style: '--gc:' + (gp.color || '#8893a6') }));

  const centrado = isCentered(forma);
  const ic = !centrado && n.icon !== 'none' ? (ICN[n.icon] || ICN['box']) : null;
  if (ic) {
    const ig = mk('g', { transform: `translate(15,${NH / 2 - 11})`, class: 'ico' });
    ig.appendChild(mk('svg', { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
                               'stroke-width': 1.7, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, ic));
    g.appendChild(ig);
  }
  const inset = textInset(forma, NW);
  const t = mk('text', centrado
    ? { x: NW / 2, y: NH / 2 + 4.5, class: 'nlabel mid', 'text-anchor': 'middle' }
    : { x: ic ? 45 : inset, y: NH / 2 + 4.5, class: 'nlabel' });
  t.textContent = ajustarTexto(n.label || n.id, NW - 2 * inset, centrado);
  g.appendChild(t);
  if (n.note) g.appendChild(mk('circle', { cx: NW - 12, cy: 12, r: 3, class: 'noteDot' }));
  // uma porta por lado: é o que permite ligar por cima/baixo além dos lados
  SIDES.forEach(side => {
    const a = anchorSide([0, 0], side, NW, NH);
    g.appendChild(mk('circle', { cx: a[0], cy: a[1], r: 6, class: 'port', 'data-side': side }));
  });
  bindNode(g, n);
  return g;
}
