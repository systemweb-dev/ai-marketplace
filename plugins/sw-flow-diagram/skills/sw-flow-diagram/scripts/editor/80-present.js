/* ---- modo apresentação: percorre o diagrama por estágios ----
   Em diagrama grande, mostrar tudo de uma vez é o mesmo que não mostrar nada.
   Aqui cada passo acende um trecho e escurece o resto, com a câmera acompanhando. */
let present = { on: false, passo: 0, etapas: [] };

/** Etapas em ordem topológica: cada uma é o conjunto de nós alcançados naquele "nível".
    Nós sem predecessor abrem; ciclos não travam (o que sobra entra como etapa final). */
function montarEtapas() {
  const nos = (F.nodes || []).filter(nodeVisible).map(n => n.id);
  const dentro = new Set(nos);
  const grau = {}; nos.forEach(id => grau[id] = 0);
  const saida = {}; nos.forEach(id => saida[id] = []);
  (F.edges || []).forEach(e => {
    if (!dentro.has(e.from) || !dentro.has(e.to) || e.from === e.to) return;
    grau[e.to]++; saida[e.from].push(e.to);
  });
  const etapas = [];
  let atual = nos.filter(id => grau[id] === 0);
  const visto = new Set(atual);
  while (atual.length) {
    etapas.push(atual);
    const prox = [];
    atual.forEach(id => saida[id].forEach(t => {
      if (--grau[t] === 0 && !visto.has(t)) { visto.add(t); prox.push(t); }
    }));
    atual = prox;
  }
  const restantes = nos.filter(id => !visto.has(id));
  if (restantes.length) etapas.push(restantes);
  return etapas.length ? etapas : [nos];
}

/** Nós acesos até o passo atual (acumulativo: o caminho já percorrido continua visível). */
function acesos() {
  const s = new Set();
  for (let i = 0; i <= present.passo && i < present.etapas.length; i++) present.etapas[i].forEach(id => s.add(id));
  return s;
}
const dimmedNode = id => present.on && !acesos().has(id);
const dimmed = (a, b) => {
  if (!present.on) return false;
  const on = acesos();
  const vale = k => String(k).startsWith('g:') ? nodesOfGroup(String(k).slice(2)).some(n => on.has(n.id)) : on.has(k);
  return !(vale(a) && vale(b));
};

function presentStart() {
  present.on = true; present.passo = 0; present.etapas = montarEtapas();
  clearSel();
  document.body.classList.add('presenting');
  render(); presentFocus();
  atualizarBarra();
}
function presentStop() {
  present.on = false;
  document.body.classList.remove('presenting');
  const b = document.querySelector('.pbar'); if (b) b.remove();
  render(); fitView(true);
}
function presentGo(delta) {
  const n = present.passo + delta;
  if (n < 0) return;
  if (n >= present.etapas.length) { presentStop(); return; }
  present.passo = n;
  render(); presentFocus(); atualizarBarra();
}
function presentFocus() {
  const etapa = present.etapas[present.passo] || [];
  const anterior = present.etapas[present.passo - 1] || [];
  focusNodes([...new Set([...etapa, ...anterior])], 1.15);
}
function atualizarBarra() {
  let bar = document.querySelector('.pbar');
  if (!bar) {
    bar = h('div', 'pbar');
    document.body.appendChild(bar);
  }
  const total = present.etapas.length;
  const nomes = (present.etapas[present.passo] || []).map(id => {
    const n = nodeById(id); return n ? (n.label || n.id) : id;
  });
  bar.innerHTML = `<button data-a="prev" title="Anterior (←)">‹</button>`
    + `<div class="pinfo"><b>Etapa ${present.passo + 1} de ${total}</b><span>${nomes.join(' · ')}</span></div>`
    + `<button data-a="next" title="Próxima (→)">›</button>`
    + `<button data-a="exit" class="x" title="Sair (Esc)">Sair</button>`;
  bar.querySelector('[data-a="prev"]').onclick = () => presentGo(-1);
  bar.querySelector('[data-a="next"]').onclick = () => presentGo(1);
  bar.querySelector('[data-a="exit"]').onclick = presentStop;
}
