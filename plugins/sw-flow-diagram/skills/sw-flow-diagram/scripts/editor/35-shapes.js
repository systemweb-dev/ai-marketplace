/* ---- formas de fluxograma ----
   Cada forma é desenhada dentro da MESMA caixa NW×NH que o layout já reserva. Manter a
   caixa constante é o que permite trocar a forma de um nó sem recalcular posições nem
   re-rotear as setas — as âncoras continuam onde estavam. */
const SHAPES = [
  { id: 'rounded',   label: 'Processo',            hint: 'etapa comum',            center: false },
  { id: 'rect',      label: 'Retângulo',           hint: 'caixa reta',             center: false },
  { id: 'stadium',   label: 'Início / Fim',        hint: 'terminador',             center: true  },
  { id: 'diamond',   label: 'Decisão',             hint: 'sim / não',              center: true  },
  { id: 'parallel',  label: 'Entrada / Saída',     hint: 'dado',                   center: true  },
  { id: 'cylinder',  label: 'Banco de dados',      hint: 'armazenamento',          center: true  },
  { id: 'circle',    label: 'Conector',            hint: 'liga trechos',           center: true  },
  { id: 'hexagon',   label: 'Preparação',          hint: 'laço / setup',           center: true  },
  { id: 'document',  label: 'Documento',           hint: 'relatório, arquivo',     center: true  },
  { id: 'docs',      label: 'Vários documentos',   hint: 'lote',                   center: true  },
  { id: 'subroutine',label: 'Subprocesso',         hint: 'processo definido fora', center: false },
  { id: 'manual',    label: 'Entrada manual',      hint: 'digitação',              center: true  },
  { id: 'operation', label: 'Operação manual',     hint: 'passo humano',           center: true  },
  { id: 'delay',     label: 'Espera',              hint: 'atraso, fila',           center: true  },
  { id: 'display',   label: 'Exibição',            hint: 'tela, saída visual',     center: true  },
  { id: 'storage',   label: 'Armazenamento',       hint: 'disco, volume',          center: true  },
  { id: 'merge',     label: 'Junção',              hint: 'converge caminhos',      center: true  },
  { id: 'extract',   label: 'Separação',           hint: 'divide caminhos',        center: true  },
  { id: 'offpage',   label: 'Fora da página',      hint: 'continua noutro ponto',  center: true  },
  { id: 'cloud',     label: 'Nuvem / externo',     hint: 'serviço de terceiro',    center: true  },
  { id: 'note',      label: 'Anotação',            hint: 'comentário',             center: false },
];
const SHAPE_BY_ID = Object.fromEntries(SHAPES.map(s => [s.id, s]));
const isCentered = id => (SHAPE_BY_ID[id] || SHAPE_BY_ID.rounded).center;

/* Detalhe em pixel (raio do canto, barra, dobra) encolhe junto com a caixa: a miniatura da
   paleta usa uma caixa bem menor que a do nó, e raio fixo transformava "Processo" em pílula. */
const kDet = (w, hh) => Math.min(1, (window.NW ? w / window.NW : 1), (window.NH ? hh / window.NH : 1));

/** Devolve {tag, attrs} do contorno da forma, inscrito em w×h. */
function shapeGeom(id, w, hh) {
  const k = kDet(w, hh), r = 13 * k, m = Math.min(w, hh);
  switch (id) {
    case 'rect':      return { tag: 'rect', attrs: { x: 0, y: 0, width: w, height: hh, rx: 2 } };
    case 'stadium':   return { tag: 'rect', attrs: { x: 0, y: 0, width: w, height: hh, rx: hh / 2 } };
    case 'circle':    return { tag: 'ellipse', attrs: { cx: w / 2, cy: hh / 2, rx: w / 2, ry: hh / 2 } };
    case 'diamond':   return { tag: 'path', attrs: { d: `M${w / 2},0 L${w},${hh / 2} L${w / 2},${hh} L0,${hh / 2} Z` } };
    case 'parallel':  return { tag: 'path', attrs: { d: `M${w * .18},0 L${w},0 L${w * .82},${hh} L0,${hh} Z` } };
    case 'hexagon':   return { tag: 'path', attrs: { d: `M${w * .16},0 L${w * .84},0 L${w},${hh / 2} L${w * .84},${hh} L${w * .16},${hh} L0,${hh / 2} Z` } };
    case 'manual':    return { tag: 'path', attrs: { d: `M0,${hh * .26} L${w},0 L${w},${hh} L0,${hh} Z` } };
    case 'operation': return { tag: 'path', attrs: { d: `M0,0 L${w},0 L${w * .84},${hh} L${w * .16},${hh} Z` } };
    case 'offpage':   return { tag: 'path', attrs: { d: `M0,0 L${w},0 L${w},${hh * .62} L${w / 2},${hh} L0,${hh * .62} Z` } };
    case 'delay':     return { tag: 'path', attrs: { d: `M0,0 L${w - hh / 2},0 A${hh / 2},${hh / 2} 0 0 1 ${w - hh / 2},${hh} L0,${hh} Z` } };
    case 'display':   return { tag: 'path', attrs: { d: `M${hh * .22},0 L${w - hh / 2},0 A${hh / 2},${hh / 2} 0 0 1 ${w - hh / 2},${hh} L${hh * .22},${hh} L0,${hh / 2} Z` } };
    case 'cylinder': {
      const e = hh * .17;
      return { tag: 'path', attrs: { d: `M0,${e} A${w / 2},${e} 0 0 1 ${w},${e} L${w},${hh - e} A${w / 2},${e} 0 0 1 0,${hh - e} Z` } };
    }
    case 'document':  return { tag: 'path', attrs: { d: `M0,0 L${w},0 L${w},${hh * .82} Q${w * .75},${hh} ${w / 2},${hh * .9} T0,${hh * .82} Z` } };
    case 'docs': {
      // folha da FRENTE em baixo-à-direita; as de trás saem em shapeExtras, acima-à-esquerda
      const dx = w * .07, dy = hh * .17;
      const bw = w - dx;
      return { tag: 'path', attrs: { d: `M${dx},${dy} L${w},${dy} L${w},${hh * .82} Q${dx + bw * .75},${hh} ${dx + bw / 2},${hh * .9} T${dx},${hh * .82} Z` } };
    }
    case 'subroutine':return { tag: 'rect', attrs: { x: 0, y: 0, width: w, height: hh, rx: 3 * k } };
    case 'storage':   return { tag: 'path', attrs: { d: `M${hh * .22},0 L${w},0 Q${w - hh * .22},${hh / 2} ${w},${hh} L${hh * .22},${hh} Q0,${hh / 2} ${hh * .22},0 Z` } };
    case 'merge':     return { tag: 'path', attrs: { d: `M0,0 L${w},0 L${w / 2},${hh} Z` } };
    case 'extract':   return { tag: 'path', attrs: { d: `M${w / 2},0 L${w},${hh} L0,${hh} Z` } };
    case 'cloud': {
      const k = hh / 2;
      return { tag: 'path', attrs: { d: `M${w * .24},${hh} A${k * .78},${k * .78} 0 0 1 ${w * .22},${hh * .42} A${k * .82},${k * .82} 0 0 1 ${w * .52},${hh * .16} A${k * .78},${k * .78} 0 0 1 ${w * .8},${hh * .44} A${k * .72},${k * .72} 0 0 1 ${w * .78},${hh} Z` } };
    }
    case 'note':      return { tag: 'path', attrs: { d: `M0,0 L${w - 16 * k},0 L${w},${16 * k} L${w},${hh} L0,${hh} Z` } };
    default:          return { tag: 'rect', attrs: { x: 0, y: 0, width: w, height: hh, rx: r } };
  }
}
/** Enfeites que não cabem no contorno (as barras do subprocesso, a dobra da anotação). */
function shapeExtras(id, w, hh) {
  const k = kDet(w, hh);
  if (id === 'subroutine') return [
    { tag: 'line', attrs: { x1: 11 * k, y1: 0, x2: 11 * k, y2: hh, class: 'nedge' } },
    { tag: 'line', attrs: { x1: w - 11 * k, y1: 0, x2: w - 11 * k, y2: hh, class: 'nedge' } }];
  if (id === 'note') return [
    // fill:none explícito — sem isso o triângulo da dobra herda preenchimento preto
    { tag: 'path', attrs: { d: `M${w - 16 * k},0 L${w - 16 * k},${16 * k} L${w},${16 * k}`, class: 'nedge', fill: 'none' } }];
  if (id === 'cylinder') {
    const e = hh * .17;
    // aresta frontal da tampa: é ela que dá a leitura de cilindro em vez de barril
    return [{ tag: 'path', attrs: { d: `M0,${e} A${w / 2},${e} 0 0 0 ${w},${e}`, class: 'nedge', fill: 'none' } }];
  }
  if (id === 'docs') {
    // duas folhas atrás: só a borda superior e um toco de lateral — o resto fica escondido
    // pela folha da frente, que é o que produz a leitura de pilha
    const dx = w * .07, dy = hh * .17, bw = w - dx, stub = hh * .12;
    return [2, 1].map(k => {
      const ox = dx - (dx / 2) * k, oy = dy - (dy / 2) * k;
      return { tag: 'path', attrs: {
        d: `M${ox},${oy + stub} L${ox},${oy} L${ox + bw},${oy} L${ox + bw},${oy + stub}`,
        class: 'nedge', fill: 'none' } };
    });
  }
  return [];
}
/** Área útil de texto: formas com bico/ponta perdem largura nas bordas. */
function textInset(id, w) {
  if (id === 'diamond') return w * .22;
  if (['parallel', 'hexagon', 'operation', 'merge', 'extract', 'cloud'].includes(id)) return w * .17;
  if (['delay', 'display', 'storage'].includes(id)) return w * .12;
  return 14;
}
