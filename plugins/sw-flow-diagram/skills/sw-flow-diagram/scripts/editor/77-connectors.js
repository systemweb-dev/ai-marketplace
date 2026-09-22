/* ---- conectores legíveis: paralelas que não se escondem ----
   Duas conexões entre os mesmos dois nós (ida e volta, ou dois protocolos) saíam desenhadas
   uma EM CIMA da outra: o diagrama mentia, mostrando uma seta onde havia duas. Aqui cada
   par ganha um leque de deslocamentos, calculado só a partir da ordem no documento — o
   mesmo flow.json desenha sempre igual, e ida e volta continuam sendo duas setas. */
const EDGE_GAP = 15;

/** Chave do par, sem direção: ida e volta compartilham o mesmo leque. */
function pairKey(a, b) {
  return a < b ? a + '|' + b : b + '|' + a;
}

/** Deslocamento de cada aresta visível, em pixels, perpendicular ao traço.
    `resolve` traduz um id de nó no que ele representa na tela (o grupo, se recolhido). */
function parallelOffsets(edges, resolve, gap) {
  const passo = gap || EDGE_GAP;
  const id = resolve || (x => x);
  const baldes = new Map();
  const representante = new Map();             // linha desenhada -> índice que a representa
  const copia = new Map();                     // índice fundido -> índice do representante
  (edges || []).forEach((ed, i) => {
    const a = id(ed.from), b = id(ed.to);
    if (a === b) return;                       // some no grupo recolhido: não ocupa lugar no leque
    const direcao = a + '>' + b;
    if (representante.has(direcao)) { copia.set(i, representante.get(direcao)); return; }
    representante.set(direcao, i);             // a vaga no leque é por LINHA desenhada,
    const k = pairKey(a, b);                   // não por aresta do documento: as fundidas
    if (!baldes.has(k)) baldes.set(k, []);     // pelo grupo recolhido viram uma só.
    baldes.get(k).push(i);
  });
  const offsets = new Array((edges || []).length).fill(0);
  baldes.forEach(indices => {
    if (indices.length < 2) return;
    indices.forEach((idx, pos) => { offsets[idx] = (pos - (indices.length - 1) / 2) * passo; });
  });
  copia.forEach((rep, idx) => { offsets[idx] = offsets[rep]; });
  return offsets;
}

/** Quantas arestas do documento cada par visível representa. Com um grupo recolhido, várias
    viram uma só na tela — e o número é o que impede a leitura errada de "há uma conexão". */
function mergedCounts(edges, resolve) {
  const id = resolve || (x => x);
  const contagem = new Map();
  (edges || []).forEach(ed => {
    const a = id(ed.from), b = id(ed.to);
    if (a === b) return;
    const k = a + '>' + b;
    contagem.set(k, (contagem.get(k) || 0) + 1);
  });
  return contagem;
}

/** Move um ponto de ancoragem ao longo do lado de onde ele sai (o traço anda de lado,
    não para frente: o leque abre sem mudar de qual borda a seta parte). */
function shiftAnchor(point, side, offset) {
  if (!offset) return point;
  return (side === 'left' || side === 'right')
    ? [point[0], point[1] + offset]
    : [point[0] + offset, point[1]];
}

if (typeof module === 'object' && module.exports) {
  module.exports = { pairKey, parallelOffsets, mergedCounts, shiftAnchor, EDGE_GAP };
}
