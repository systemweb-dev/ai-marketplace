/* ---- paletas e edição inline de rótulo ---- */
function fecharAoClicarFora(el) {
  setTimeout(() => document.addEventListener('pointerdown', function fn(e) {
    if (!el.contains(e.target)) { el.remove(); document.removeEventListener('pointerdown', fn); }
  }), 0);
}

/** Paleta do catálogo: escolhe um componente pronto (rótulo + ícone) ou nó em branco. */
function componentPalette(sx, sy, pt) {
  document.querySelectorAll('.cpal').forEach(e => e.remove());
  const pal = h('div', 'cpal');
  const busca = h('input', 'srch'); busca.placeholder = 'Buscar componente…';
  const corpo = h('div');
  pal.appendChild(busca); pal.appendChild(corpo);
  function desenhar(q) {
    corpo.innerHTML = ''; q = (q || '').toLowerCase().trim();
    CAT.forEach(grupo => {
      const itens = (grupo.items || []).filter(it => !q || it.label.toLowerCase().includes(q));
      if (!itens.length) return;
      corpo.appendChild(h('h4', null, grupo.cat));
      const grid = h('div', 'grid');
      itens.forEach(it => {
        const b = document.createElement('button');
        b.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICN[it.icon] || ICN['box']}</svg><span>${it.label}</span>`;
        b.onclick = () => { beginChange(); const id = addNode(pt, it.label, it.icon); selectNode(id); pal.remove(); render(); };
        grid.appendChild(b);
      });
      corpo.appendChild(grid);
    });
    const wrap = h('div', 'grid');
    const vazio = h('button', 'blank', '+ Nó em branco');
    vazio.onclick = () => { beginChange(); const id = addNode(pt, 'Novo', 'box'); selectNode(id); pal.remove(); render(); setTimeout(() => editLabel('n', id), 0); };
    wrap.appendChild(vazio); corpo.appendChild(wrap);
  }
  desenhar('');
  busca.addEventListener('input', () => desenhar(busca.value));
  busca.addEventListener('keydown', e => {
    if (e.key === 'Escape') pal.remove();
    if (e.key === 'Enter') { const p = corpo.querySelector('.grid button:not(.blank)'); if (p) p.click(); }
  });
  pal.style.left = Math.min(sx - 20, innerWidth - 330) + 'px';
  pal.style.top = Math.min(sy - 10, innerHeight - 80) + 'px';
  document.body.appendChild(pal); busca.focus();
  fecharAoClicarFora(pal);
}

/** Busca de nós — indispensável quando o diagrama passa de algumas dezenas de caixas. */
function abrirBusca() {
  document.querySelectorAll('.fsearch').forEach(e => e.remove());
  const box = h('div', 'fsearch');
  const inp = h('input'); inp.placeholder = 'Ir para o nó…';
  const lista = h('div', 'res');
  box.appendChild(inp); box.appendChild(lista);
  document.body.appendChild(box); inp.focus();
  let marcado = 0, atuais = [];
  function desenhar() {
    const q = inp.value.toLowerCase().trim();
    atuais = (F.nodes || []).filter(n => !q || (n.label || n.id).toLowerCase().includes(q)).slice(0, 12);
    lista.innerHTML = '';
    atuais.forEach((n, i) => {
      const b = document.createElement('button');
      if (i === marcado) b.className = 'on';
      const gp = n.group && groupById(n.group);
      b.innerHTML = `<span>${n.label || n.id}</span>` + (gp ? `<em>${gp.label || gp.id}</em>` : '');
      b.onclick = () => irPara(n.id);
      lista.appendChild(b);
    });
  }
  function irPara(id) {
    const n = nodeById(id);
    if (n && n.group && COLLAPSED.has(n.group)) COLLAPSED.delete(n.group);   // abre o grupo p/ mostrar
    clearSel(); selectNode(id); render();
    focusNodes([id], 1.1);
    box.remove();
  }
  inp.addEventListener('input', () => { marcado = 0; desenhar(); });
  inp.addEventListener('keydown', e => {
    if (e.key === 'Escape') box.remove();
    if (e.key === 'ArrowDown') { marcado = Math.min(atuais.length - 1, marcado + 1); desenhar(); e.preventDefault(); }
    if (e.key === 'ArrowUp') { marcado = Math.max(0, marcado - 1); desenhar(); e.preventDefault(); }
    if (e.key === 'Enter' && atuais[marcado]) irPara(atuais[marcado].id);
  });
  desenhar();
  fecharAoClicarFora(box);
}

/** Edição do rótulo direto sobre o elemento. */
let editando = null;
const isEditing = () => !!editando;
function editLabel(tipo, chave) {
  const inp = h('input', 'inlED');
  editando = inp;
  let cx, cy, w, atual;
  if (tipo === 'n') {
    const p = POS[chave]; atual = nodeById(chave).label || '';
    const sp = toScreen(p[0] + NW / 2, p[1] + NH / 2);
    cx = sp.x; cy = sp.y; w = NW - 30;
  } else {
    const ed = F.edges[chave];
    const geo = edgeGeom(ed);
    if (!geo) { editando = null; return; }
    atual = ed.label || '';
    const sp = toScreen((geo.p1[0] + geo.p2[0]) / 2, (geo.p1[1] + geo.p2[1]) / 2 - 8);
    cx = sp.x; cy = sp.y; w = 130;
  }
  inp.value = atual;
  inp.style.left = (cx - w / 2) + 'px'; inp.style.top = (cy - 14) + 'px'; inp.style.width = w + 'px';
  document.body.appendChild(inp); inp.focus(); inp.select();
  let fechado = false;
  const done = salvar => {
    if (fechado) return; fechado = true;
    const v = inp.value.trim();
    if (salvar && v !== atual) {
      beginChange();
      if (tipo === 'n') nodeById(chave).label = v || 'Nó';
      else if (v) F.edges[chave].label = v; else delete F.edges[chave].label;
    }
    inp.remove(); editando = null; render();
  };
  inp.addEventListener('keydown', e => { if (e.key === 'Enter') done(true); if (e.key === 'Escape') done(false); });
  inp.addEventListener('blur', () => done(true));
}
