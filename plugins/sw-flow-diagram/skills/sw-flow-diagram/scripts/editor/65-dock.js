/* ---- paleta fixa lateral: arraste o componente para dentro do diagrama ----
   O duplo-clique no vazio continua valendo, mas exige saber que existe. Uma paleta
   sempre visível mostra o que dá pra usar, e arrastar é o gesto que as pessoas já
   trazem de Miro/Whimsical. */
const dock = h('aside', 'fdock');
document.body.appendChild(dock);

let dockAberto = true;
function montarDock() {
  dock.innerHTML = '';
  const topo = h('div', 'dkh');
  topo.appendChild(h('span', null, 'Componentes'));
  const tog = h('button', 'dktog', dockAberto ? '‹' : '›');
  tog.title = dockAberto ? 'Recolher paleta' : 'Abrir paleta';
  tog.onclick = () => { dockAberto = !dockAberto; dock.classList.toggle('closed', !dockAberto); /** Miniatura da forma para a paleta (mesma geometria do render, em caixa 40×28). */
function miniForma(id) {
  const g = shapeGeom(id, 38, 26);
  const at = Object.entries({ ...g.attrs, transform: 'translate(1,1)' })
    .map(([k, v]) => `${k}="${v}"`).join(' ');
  const ex = shapeExtras(id, 38, 26)
    .map(e => `<${e.tag} ${Object.entries(e.attrs).filter(([k]) => k !== 'class').map(([k, v]) => `${k}="${v}"`).join(' ')} transform="translate(1,1)"/>`).join('');
  return `<${g.tag} ${at}/>${ex}`;
}
montarDock(); };
  topo.appendChild(tog);
  dock.appendChild(topo);
  if (!dockAberto) return;

  const busca = h('input', 'dksrch');
  busca.placeholder = 'Buscar…';
  dock.appendChild(busca);
  const corpo = h('div', 'dkbody');
  dock.appendChild(corpo);

  function desenhar(q) {
    corpo.innerHTML = '';
    q = (q || '').toLowerCase().trim();
    // formas primeiro: é o vocabulário de fluxograma, independe do catálogo de infra
    const formas = SHAPES.filter(s => !q || s.label.toLowerCase().includes(q) || s.hint.includes(q));
    if (formas.length) {
      corpo.appendChild(h('h5', null, 'Formas'));
      const gridF = h('div', 'dkgrid');
      formas.forEach(s => {
        const b = h('button', 'dkit');
        b.title = s.hint + ' — arraste para o diagrama';
        b.innerHTML = `<svg class="shp" width="21" height="15" viewBox="0 0 40 28">${miniForma(s.id)}</svg><span>${s.label}</span>`;
        b.addEventListener('pointerdown', ev => arrastarDoDock(ev, { label: s.label, icon: 'box', shape: s.id }));
        gridF.appendChild(b);
      });
      corpo.appendChild(gridF);
    }
    CAT.forEach(grupo => {
      const itens = (grupo.items || []).filter(it => !q || it.label.toLowerCase().includes(q));
      if (!itens.length) return;
      corpo.appendChild(h('h5', null, grupo.cat));
      const grid = h('div', 'dkgrid');
      itens.forEach(it => {
        const b = h('button', 'dkit');
        b.title = 'Arraste para o diagrama (ou clique)';
        b.innerHTML = `<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICN[it.icon] || ICN['box']}</svg><span>${it.label}</span>`;
        b.addEventListener('pointerdown', ev => arrastarDoDock(ev, it));
        grid.appendChild(b);
      });
      corpo.appendChild(grid);
    });
    if (!corpo.children.length) corpo.appendChild(h('p', 'dkempty', 'Nada encontrado.'));
  }
  desenhar('');
  busca.addEventListener('input', () => desenhar(busca.value));
}

/** Arrasta um item da paleta até o canvas. Solta fora do canvas = cancela. */
function arrastarDoDock(ev, item) {
  ev.preventDefault();
  const fantasma = h('div', 'dkghost');
  fantasma.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICN[item.icon] || ICN['box']}</svg><span>${item.label}</span>`;
  document.body.appendChild(fantasma);
  const mover = e => {
    fantasma.style.left = (e.clientX + 12) + 'px';
    fantasma.style.top = (e.clientY + 12) + 'px';
    const sobre = dentroDoCanvas(e);
    fantasma.classList.toggle('ok', sobre);
  };
  mover(ev);
  const soltar = e => {
    window.removeEventListener('pointermove', mover);
    window.removeEventListener('pointerup', soltar);
    fantasma.remove();
    if (!dentroDoCanvas(e)) return;                       // soltou fora: não cria nada
    const p = toSvg(e);
    beginChange();
    const id = addNode([p.x, p.y], item.label, item.icon, grupoSob(p));
    if (item.shape) nodeById(id).shape = item.shape;
    clearSel(); selectNode(id);
    render();
  };
  window.addEventListener('pointermove', mover);
  window.addEventListener('pointerup', soltar);
}
function dentroDoCanvas(e) {
  const r = stage.getBoundingClientRect();
  if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) return false;
  return !(dock.contains(e.target) || panel.contains(e.target));
}
/** Se soltou dentro da caixa de um grupo, o nó já nasce nele — é o que a pessoa espera
    ao arrastar para dentro de uma área nomeada. */
function grupoSob(p) {
  let achado = null;
  (F.groups || []).forEach(g => {
    if (COLLAPSED.has(g.id)) return;
    const b = groupBBox(g.id);
    if (b && p.x >= b[0] - 16 && p.x <= b[2] + 16 && p.y >= b[1] - 30 && p.y <= b[3] + 16) achado = g.id;
  });
  return achado;
}
/** Miniatura da forma para a paleta (mesma geometria do render, em caixa 40×28). */
function miniForma(id) {
  const g = shapeGeom(id, 38, 26);
  const at = Object.entries({ ...g.attrs, transform: 'translate(1,1)' })
    .map(([k, v]) => `${k}="${v}"`).join(' ');
  const ex = shapeExtras(id, 38, 26)
    .map(e => `<${e.tag} ${Object.entries(e.attrs).filter(([k]) => k !== 'class').map(([k, v]) => `${k}="${v}"`).join(' ')} transform="translate(1,1)"/>`).join('');
  return `<${g.tag} ${at}/>${ex}`;
}
montarDock();
