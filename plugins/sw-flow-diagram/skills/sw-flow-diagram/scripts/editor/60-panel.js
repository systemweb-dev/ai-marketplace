/* ---- painel de propriedades (lateral) ----
   Reúne num lugar só o que antes exigia caçar botão: rótulo, ícone, grupo, nota,
   e o estilo da conexão. */
const panel = h('aside', 'fpanel');
document.body.appendChild(panel);

/** A largura útil do palco muda quando o painel abre/fecha; sem reaplicar a câmera o
    viewBox fica com o tamanho antigo e o diagrama aparece esticado. */
function ajustarCamera() { setTimeout(() => applyCam(), 190); }

function campo(rotulo, ctrl) {
  const w = h('label', 'fld');
  w.appendChild(h('span', 'fl', rotulo));
  w.appendChild(ctrl);
  return w;
}
function editarNota(n) {
  const ta = h('textarea', 'fta');
  ta.value = n.note || '';
  ta.placeholder = 'Explicação que aparece no diagrama e no tooltip…';
  ta.addEventListener('change', () => {
    beginChange();
    const v = ta.value.trim();
    if (v) n.note = v; else delete n.note;
    render();
  });
  return ta;
}

function renderPanel() {
  const ids = selNodeIds();
  const estavaAberto = panel.classList.contains('open');
  if (!hasSel()) {
    panel.classList.remove('open'); panel.innerHTML = '';
    if (estavaAberto) ajustarCamera();
    return;
  }
  panel.classList.add('open');
  if (!estavaAberto) ajustarCamera();
  panel.innerHTML = '';

  // ---- vários nós selecionados: ações em lote
  if (ids.length > 1) {
    panel.appendChild(h('div', 'ph', `<b>${ids.length} itens</b><span>selecionados</span>`));
    const gsel = h('select', 'fsel');
    gsel.innerHTML = '<option value="">— manter —</option><option value="__none">Sem grupo</option>'
      + (F.groups || []).map(g => `<option value="${g.id}">${g.label || g.id}</option>`).join('')
      + '<option value="__new">+ Novo grupo…</option>';
    gsel.addEventListener('change', () => {
      const v = gsel.value; if (!v) return;
      let gid = v;
      if (v === '__new') { const nome = prompt('Nome do grupo:'); if (!nome) { gsel.value = ''; return; } beginChange(); gid = ensureGroup(nome); }
      else beginChange();
      ids.forEach(id => { const n = nodeById(id); if (!n) return; if (gid === '__none') delete n.group; else n.group = gid; });
      render();
    });
    panel.appendChild(campo('Mover para o grupo', gsel));
    const bDup = h('button', 'fbtn', 'Duplicar (Ctrl+D)');
    bDup.onclick = () => duplicarSelecao();
    const bDel = h('button', 'fbtn danger', 'Excluir (Del)');
    bDel.onclick = () => excluirSelecao();
    const acoes = h('div', 'frow'); acoes.appendChild(bDup); acoes.appendChild(bDel);
    panel.appendChild(acoes);
    return;
  }

  // ---- uma conexão
  if (sel.edge !== null && F.edges[sel.edge]) {
    const ed = F.edges[sel.edge];
    const de = nodeById(ed.from), para = nodeById(ed.to);
    panel.appendChild(h('div', 'ph', `<b>Conexão</b><span>${(de && de.label) || ed.from} → ${(para && para.label) || ed.to}</span>`));
    const lab = h('input', 'finp'); lab.value = ed.label || ''; lab.placeholder = 'ex.: 443, async, cache miss';
    lab.addEventListener('change', () => { beginChange(); const v = lab.value.trim(); if (v) ed.label = v; else delete ed.label; render(); });
    panel.appendChild(campo('Rótulo', lab));
    const est = h('select', 'fsel');
    est.innerHTML = '<option value="solid">Contínua</option><option value="dashed">Tracejada</option>';
    est.value = ed.style === 'dashed' ? 'dashed' : 'solid';
    est.addEventListener('change', () => { beginChange(); if (est.value === 'dashed') ed.style = 'dashed'; else delete ed.style; render(); });
    panel.appendChild(campo('Traço', est));
    const anim = h('input'); anim.type = 'checkbox'; anim.checked = ed.animated !== false;
    anim.addEventListener('change', () => { beginChange(); ed.animated = anim.checked; render(); });
    const wrapA = h('label', 'fchk'); wrapA.appendChild(anim); wrapA.appendChild(h('span', null, 'Animar o fluxo nesta conexão'));
    panel.appendChild(wrapA);
    const bInv = h('button', 'fbtn', 'Inverter sentido');
    bInv.onclick = () => { beginChange(); const t = ed.from; ed.from = ed.to; ed.to = t; render(); };
    const bDel = h('button', 'fbtn danger', 'Excluir');
    bDel.onclick = () => excluirSelecao();
    const acoes = h('div', 'frow'); acoes.appendChild(bInv); acoes.appendChild(bDel);
    panel.appendChild(acoes);
    return;
  }

  // ---- um nó
  const n = nodeById(ids[0]); if (!n) return;
  panel.appendChild(h('div', 'ph', `<b>Nó</b><span>${n.id}</span>`));
  const lab = h('input', 'finp'); lab.value = n.label || '';
  lab.addEventListener('change', () => { beginChange(); n.label = lab.value.trim() || 'Nó'; render(); });
  panel.appendChild(campo('Rótulo', lab));

  const fsel = h('select', 'fsel');
  fsel.innerHTML = SHAPES.map(s => `<option value="${s.id}">${s.label} — ${s.hint}</option>`).join('');
  fsel.value = n.shape || 'rounded';
  fsel.addEventListener('change', () => {
    beginChange();
    if (fsel.value === 'rounded') delete n.shape; else n.shape = fsel.value;
    render();
  });
  panel.appendChild(campo('Formato', fsel));

  const grid = h('div', 'fico');
  Object.keys(ICN).sort().forEach(nome => {
    const b = h('button', n.icon === nome ? 'on' : '');
    b.title = nome;
    b.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICN[nome]}</svg>`;
    b.onclick = () => { beginChange(); n.icon = nome; render(); };
    grid.appendChild(b);
  });
  if (isCentered(n.shape || 'rounded')) {
    const aviso = h('p', 'fnote', 'Esta forma usa o rótulo centralizado — o ícone não aparece nela.');
    panel.appendChild(campo('Ícone', aviso));
  } else {
    panel.appendChild(campo('Ícone', grid));
  }

  const gsel = h('select', 'fsel');
  gsel.innerHTML = '<option value="__none">Sem grupo</option>'
    + (F.groups || []).map(g => `<option value="${g.id}">${g.label || g.id}</option>`).join('')
    + '<option value="__new">+ Novo grupo…</option>';
  gsel.value = n.group || '__none';
  gsel.addEventListener('change', () => {
    const v = gsel.value;
    if (v === '__new') { const nome = prompt('Nome do grupo:'); if (!nome) { gsel.value = n.group || '__none'; return; } beginChange(); n.group = ensureGroup(nome); }
    else { beginChange(); if (v === '__none') delete n.group; else n.group = v; }
    render();
  });
  panel.appendChild(campo('Grupo', gsel));
  panel.appendChild(campo('Nota', editarNota(n)));

  const bDup = h('button', 'fbtn', 'Duplicar');
  bDup.onclick = () => duplicarSelecao();
  const bDel = h('button', 'fbtn danger', 'Excluir');
  bDel.onclick = () => excluirSelecao();
  const acoes = h('div', 'frow'); acoes.appendChild(bDup); acoes.appendChild(bDel);
  panel.appendChild(acoes);
}
