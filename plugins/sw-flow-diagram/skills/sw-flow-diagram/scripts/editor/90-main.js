/* ---- montagem: atalhos, toolbar, salvar, modo export ---- */
const QS = new URLSearchParams(location.search);
const EXPORT = QS.has('export');
const tema = QS.get('theme');
if (tema === 'dark') document.documentElement.dataset.theme = 'dark';
else if (tema === 'light') document.documentElement.removeAttribute('data-theme');

async function hashFlowOnLoad() {
  const response = await fetch('flow.json', { cache: 'no-store' });
  if (!response.ok) throw new Error('não foi possível ler o flow.json atual');
  const digest = await crypto.subtle.digest('SHA-256', await response.arrayBuffer());
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
}
const baseHashPromise = hashFlowOnLoad();

function onRender() { renderPanel(); atualizarBotoes(); }
function onCameraMove() { const p = document.querySelector('.inlED'); if (p) p.remove(); }

function excluirSelecao() {
  if (!hasSel()) return;
  beginChange();
  if (sel.edge !== null) F.edges.splice(sel.edge, 1);
  else removeNodes(selNodeIds());
  clearSel(); render();
}
function duplicarSelecao() {
  const ids = selNodeIds();
  if (!ids.length) return;
  beginChange();
  const novos = duplicateNodes(ids, 40, 40);
  clearSel(); novos.forEach(id => sel.nodes.add(id));
  render();
}
function selecionarTudo() {
  clearSel();
  (F.nodes || []).forEach(n => { if (nodeVisible(n)) sel.nodes.add(n.id); });
  render();
}

// ---- atalhos
document.addEventListener('keydown', e => {
  const mod = e.ctrlKey || e.metaKey;
  if (isEditing() || /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
    if (e.key === 'Escape') document.activeElement.blur();
    return;
  }
  if (present.on) {
    if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') { e.preventDefault(); presentGo(1); }
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); presentGo(-1); }
    if (e.key === 'Escape') presentStop();
    return;
  }
  if (mod && e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); if (undo()) { clearSel(); render(); } return; }
  if (mod && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) { e.preventDefault(); if (redo()) { clearSel(); render(); } return; }
  if (mod && e.key.toLowerCase() === 'd') { e.preventDefault(); duplicarSelecao(); return; }
  if (mod && e.key.toLowerCase() === 'a') { e.preventDefault(); selecionarTudo(); return; }
  if (mod && e.key.toLowerCase() === 'f') { e.preventDefault(); abrirBusca(); return; }
  if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); salvar(false); return; }
  if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); excluirSelecao(); return; }
  if (e.key === 'Escape') { clearSel(); render(); return; }
  if (e.key === '=' || e.key === '+') { zoomBy(1.15); return; }
  if (e.key === '-') { zoomBy(1 / 1.15); return; }
  if (e.key === '0') { fitView(true); return; }
  // setas movem a seleção (1px, ou 10 com Shift)
  if (/^Arrow/.test(e.key) && sel.nodes.size) {
    e.preventDefault();
    const d = e.shiftKey ? 10 : 1;
    const dx = e.key === 'ArrowRight' ? d : e.key === 'ArrowLeft' ? -d : 0;
    const dy = e.key === 'ArrowDown' ? d : e.key === 'ArrowUp' ? -d : 0;
    beginChange();
    selNodeIds().forEach(id => { if (POS[id]) POS[id] = [Math.max(0, POS[id][0] + dx), Math.max(0, POS[id][1] + dy)]; });
    render();
  }
});

// ---- fundo: duplo-clique adiciona · arrasto faz pan (ou laço com Shift)
svg.addEventListener('dblclick', e => {
  if (present.on) return;
  const bg = e.target === svg || e.target.classList.contains('gbox') || e.target.classList.contains('lbox');
  if (!bg) return;
  const l = toSvg(e);
  componentPalette(e.clientX, e.clientY, [l.x, l.y]);
});

if (!EXPORT) {
  fitView();
  window.addEventListener('resize', () => applyCam());
  stage.addEventListener('wheel', e => {
    e.preventDefault();
    zoomBy(e.deltaY < 0 ? 1.12 : 1 / 1.12, e.clientX, e.clientY);
  }, { passive: false });

  svg.addEventListener('pointerdown', e => {
    const bg = e.target === svg || e.target.classList.contains('gbox') || e.target.classList.contains('lbox');
    if (!bg || present.on) return;
    if (e.shiftKey) { startMarquee(e); return; }
    const sx = e.clientX, sy = e.clientY, x0 = cam.x, y0 = cam.y;
    let moveu = false;
    document.body.classList.add('panning');
    const mv = ev => {
      cam.x = x0 - (ev.clientX - sx) / cam.k; cam.y = y0 - (ev.clientY - sy) / cam.k;
      if (Math.abs(ev.clientX - sx) + Math.abs(ev.clientY - sy) > 3) moveu = true;
      applyCam();
    };
    const up = () => {
      window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up);
      document.body.classList.remove('panning');
      if (!moveu) { clearSel(); render(); }
    };
    window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up);
  });
} else {
  const b = contentBBox();
  svg.setAttribute('viewBox', `${b[0]} ${b[1]} ${b[2] - b[0]} ${b[3] - b[1]}`);
  svg.setAttribute('width', b[2] - b[0]);
  svg.setAttribute('height', b[3] - b[1]);
  document.body.classList.add('export', 'paused');
}

/* O que acontece precisa CHEGAR a quem não vê a tela: alert some do histórico e o botão
   "Salvar" muda só de cor. Toda mensagem passa por aqui e vai para a região aria-live. */
function anunciar(texto) {
  const alvo = document.getElementById('anuncio');
  if (alvo) alvo.textContent = texto;
}

// ---- salvar
async function salvar(auto) {
  const payload = structuredClone(F);
  (payload.nodes || []).forEach(n => {
    if (auto) delete n.pos;
    else if (POS[n.id]) n.pos = [Math.round(POS[n.id][0]), Math.round(POS[n.id][1])];
  });
  try {
    const baseHash = await baseHashPromise;
    const r = await fetch('/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ flow: payload, baseHash })
    });
    if (r.ok) { markSaved(); anunciar('Diagrama salvo no flow.json.'); location.reload(); }
    else {
      const erro = await r.json().catch(() => ({}));
      if (erro.code === 'conflict') {
        anunciar('Conflito: o flow.json mudou fora deste editor.');
        const recarregar = confirm('O flow.json mudou fora deste editor. Recarregar e descartar esta edição local?');
        if (recarregar) location.reload();
        else {
          const blob = new Blob([JSON.stringify(F, null, 2) + '\n'], { type: 'application/json' });
          const link = document.createElement('a');
          link.href = URL.createObjectURL(blob); link.download = 'flow-conflict.json'; link.click();
          URL.revokeObjectURL(link.href);
          alert('Edição local mantida e baixada como flow-conflict.json.');
        }
      } else {
        const msg = 'Erro ao salvar: ' + (erro.message || 'operação recusada')
          + (erro.path ? ' (em ' + erro.path + ')' : '');
        anunciar(msg);
        alert(msg);
      }
    }
  } catch (err) {
    anunciar('Sem servidor de edição: o diagrama não foi salvo.');
    alert('Sem servidor de edição. Use serve_flow.py (não o http.server) para salvar.\n' + err);
  }
}
window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });

function atualizarBotoes() {
  const u = document.getElementById('undoBtn'), r = document.getElementById('redoBtn');
  if (u) u.disabled = !canUndo();
  if (r) r.disabled = !canRedo();
  // Alteração não salva dita por extenso, não só por cor: o botão diz o que ainda falta.
  const sv = document.getElementById('savePos');
  if (sv) {
    sv.textContent = dirty ? 'Salvar alterações' : 'Salvar';
    sv.setAttribute('aria-label', dirty ? 'Salvar no flow.json. Há alterações não salvas.'
                                        : 'Salvar no flow.json. Nada mudou desde o último salvamento.');
    sv.classList.toggle('sujo', !!dirty);
  }
}
function ligar(id, fn) { const el = document.getElementById(id); if (el) el.onclick = fn; }
ligar('savePos', () => salvar(false));
ligar('autoPos', () => salvar(true));
ligar('fitBtn', () => fitView(true));
ligar('undoBtn', () => { if (undo()) { clearSel(); render(); } });
ligar('redoBtn', () => { if (redo()) { clearSel(); render(); } });
ligar('presentBtn', presentStart);
ligar('searchBtn', abrirBusca);
ligar('zoomIn', () => zoomBy(1.2));
ligar('zoomOut', () => zoomBy(1 / 1.2));

render();

// ?present na URL já abre apresentando — serve pra deixar o link pronto antes da reunião,
// sem ter que achar o botão com a sala olhando.
if (QS.has('present') && !EXPORT) {
  const passo = parseInt(QS.get('present'), 10);
  presentStart();
  if (passo > 1) for (let i = 1; i < passo; i++) presentGo(1);
}
