/* ---- edição em lote ----
   Mudar o grupo de oito nós clicando oito vezes é o tipo de trabalho que faz a pessoa
   desistir de organizar o diagrama. Estas funções aplicam uma mudança a toda a seleção,
   e quem chama abre UMA transação: o desfazer volta o lote inteiro de uma vez. */

/** Aplica os campos de `patch` a cada nó. Valor `null` apaga o campo (é o "voltar ao padrão"
    do formato e do grupo). Devolve quantos nós mudaram de fato. */
function batchNodes(flow, ids, patch) {
  const alvo = new Set(ids || []);
  let mudados = 0;
  (flow.nodes || []).forEach(n => {
    if (!alvo.has(n.id)) return;
    let mudou = false;
    Object.entries(patch || {}).forEach(([campo, valor]) => {
      if (valor === null || valor === undefined) {
        if (campo in n) { delete n[campo]; mudou = true; }
      } else if (n[campo] !== valor) { n[campo] = valor; mudou = true; }
    });
    if (mudou) mudados += 1;
  });
  return mudados;
}

/** Índices das conexões cujas duas pontas estão na seleção — as que o lote pode mexer sem
    surpresa. Uma conexão com um pé fora da seleção fica de fora de propósito. */
function edgesWithin(flow, ids) {
  const dentro = new Set(ids || []);
  const indices = [];
  (flow.edges || []).forEach((e, i) => { if (dentro.has(e.from) && dentro.has(e.to)) indices.push(i); });
  return indices;
}

/** Mesma ideia de `batchNodes`, para conexões. */
function batchEdges(flow, indices, patch) {
  let mudados = 0;
  (indices || []).forEach(i => {
    const e = (flow.edges || [])[i];
    if (!e) return;
    let mudou = false;
    Object.entries(patch || {}).forEach(([campo, valor]) => {
      if (valor === null || valor === undefined) {
        if (campo in e) { delete e[campo]; mudou = true; }
      } else if (e[campo] !== valor) { e[campo] = valor; mudou = true; }
    });
    if (mudou) mudados += 1;
  });
  return mudados;
}

/** Remove nós e, junto, as conexões que dependiam deles — conexão órfã é documento inválido
    (o contrato recusa ponta inexistente), então os dois sempre saem na mesma transação. */
function removeNodesFrom(flow, ids) {
  const set = new Set(ids || []);
  const antes = (flow.nodes || []).length + (flow.edges || []).length;
  flow.nodes = (flow.nodes || []).filter(n => !set.has(n.id));
  flow.edges = (flow.edges || []).filter(e => !set.has(e.from) && !set.has(e.to));
  return antes - ((flow.nodes || []).length + (flow.edges || []).length);
}

if (typeof module === 'object' && module.exports) {
  module.exports = { batchNodes, edgesWithin, batchEdges, removeNodesFrom };
}
