import test from 'node:test';
import assert from 'node:assert/strict';
import lote from '../scripts/editor/61-panel-actions.js';
import conectores from '../scripts/editor/77-connectors.js';
import estado from '../scripts/editor/05-state.js';

const fluxo = () => ({
  nodes: [{ id: 'a' }, { id: 'b', shape: 'diamond' }, { id: 'c', group: 'g1' }],
  edges: [{ from: 'a', to: 'b' }, { from: 'b', to: 'a' }, { from: 'a', to: 'c' }],
});

test('lote aplica a todos os selecionados e diz quantos mudaram', () => {
  const f = fluxo();

  assert.equal(lote.batchNodes(f, ['a', 'b'], { shape: 'diamond' }), 1, 'b já era diamante');
  assert.equal(f.nodes[0].shape, 'diamond');
  assert.equal(lote.batchNodes(f, ['a', 'b'], { icon: 'server' }), 2);
  assert.equal(lote.batchNodes(f, ['a'], { shape: null }), 1, 'null volta ao formato padrão');
  assert.equal('shape' in f.nodes[0], false);
});

test('o lote inteiro cabe numa transacao so: um desfazer devolve tudo', () => {
  const historia = estado.createHistory(fluxo());

  estado.transact(historia, atual => {
    lote.batchNodes(atual, ['a', 'b', 'c'], { group: 'infra' });
    return atual;
  });
  assert.deepEqual(historia.current.nodes.map(n => n.group), ['infra', 'infra', 'infra']);

  estado.undo(historia);

  assert.deepEqual(historia.current.nodes.map(n => n.group), [undefined, undefined, 'g1']);
});

test('lote de conexoes mexe so nas que tem as duas pontas na selecao', () => {
  const f = fluxo();

  const internas = lote.edgesWithin(f, ['a', 'b']);

  assert.deepEqual(internas, [0, 1]);
  assert.equal(lote.batchEdges(f, internas, { style: 'dashed', animated: false }), 2);
  assert.equal(f.edges[2].style, undefined, 'a->c tem um pé fora da seleção');
});

test('excluir nos leva junto as conexoes que dependiam deles', () => {
  const f = fluxo();

  const removidos = lote.removeNodesFrom(f, ['a']);

  assert.equal(removidos, 4, '1 nó + 3 conexões que tocavam nele');
  assert.deepEqual(f.nodes.map(n => n.id), ['b', 'c']);
  assert.deepEqual(f.edges, []);
});

test('paralelas ganham deslocamentos deterministicos e simetricos', () => {
  const edges = [{ from: 'a', to: 'b' }, { from: 'b', to: 'a' }, { from: 'a', to: 'c' }];

  const primeiro = conectores.parallelOffsets(edges, x => x, 16);

  assert.deepEqual(primeiro, [-8, 8, 0], 'o par a/b abre o leque; a->c fica na linha');
  assert.deepEqual(conectores.parallelOffsets(edges, x => x, 16), primeiro, 'mesmo documento, mesmo desenho');
});

test('ida e volta continuam sendo duas conexoes, em lados opostos', () => {
  const edges = [{ from: 'a', to: 'b' }, { from: 'b', to: 'a' }];

  const off = conectores.parallelOffsets(edges, x => x, 16);

  assert.equal(off[0], -off[1]);
  assert.notEqual(off[0], 0, 'sem deslocamento elas se escondem uma atrás da outra');
});

test('grupo recolhido funde paralelas e a contagem preserva o sentido', () => {
  const edges = [{ from: 'a', to: 'x' }, { from: 'b', to: 'x' }, { from: 'x', to: 'a' },
                 { from: 'a', to: 'b' }, { from: 'b', to: 'a' }];
  const resolve = id => (id === 'a' || id === 'b') ? 'g:infra' : id;

  const contagem = conectores.mergedCounts(edges, resolve);
  const off = conectores.parallelOffsets(edges, resolve, 16);

  assert.equal(contagem.get('g:infra>x'), 2, 'duas conexões viram uma linha só');
  assert.equal(contagem.get('x>g:infra'), 1, 'a volta é outra linha');
  assert.equal(contagem.has('g:infra>g:infra'), false, 'conexão interna ao grupo some');
  assert.deepEqual([off[3], off[4]], [0, 0], 'as duas que sumiram não abrem leque nenhum');
  assert.deepEqual([off[0], off[2]], [-8, 8], 'o leque é entre a linha de ida e a de volta');
  assert.equal(off[1], off[0], 'a fundida acompanha a linha que a representa, sem vaga própria');
});

test('o deslocamento anda pela borda, nao para frente', () => {
  assert.deepEqual(conectores.shiftAnchor([100, 50], 'right', 12), [100, 62]);
  assert.deepEqual(conectores.shiftAnchor([100, 50], 'top', 12), [112, 50]);
  assert.deepEqual(conectores.shiftAnchor([100, 50], 'right', 0), [100, 50]);
});
