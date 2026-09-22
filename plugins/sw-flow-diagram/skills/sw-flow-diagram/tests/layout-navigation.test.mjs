import test from 'node:test';
import assert from 'node:assert/strict';
import layout from '../scripts/editor/76-layout.js';
import navigation from '../scripts/editor/75-navigator.js';

globalThis.NW = 168;
globalThis.NH = 66;

test('alinha e distribui pontos selecionados', () => {
  globalThis.POS = { a: [10, 20], b: [100, 80], c: [240, 140] };
  assert.equal(layout.alignNodes(['a', 'b', 'c'], 1, 'min'), true);
  assert.deepEqual(Object.values(POS).map(p => p[1]), [20, 20, 20]);
  layout.distributeNodes(['a', 'b', 'c'], 0);
  assert.deepEqual(Object.values(POS).map(p => p[0]), [10, 125, 240]);
});

test('auto-layout e deterministico e separa camadas', () => {
  globalThis.F = { nodes: [{ id: 'b' }, { id: 'a' }, { id: 'c' }], edges: [{ from: 'a', to: 'b' }, { from: 'b', to: 'c' }] };
  globalThis.POS = {};
  const first = JSON.stringify(layout.autoLayoutModel());
  const positions = JSON.stringify(POS);
  globalThis.POS = {};
  const second = JSON.stringify(layout.autoLayoutModel());
  assert.equal(first, second);
  assert.equal(positions, JSON.stringify(POS));
});

test('foco calcula o menor caminho dirigido e nao atravessa aresta reversa', () => {
  globalThis.F = { edges: [{ from: 'a', to: 'b' }, { from: 'b', to: 'c' }, { from: 'a', to: 'c' }] };
  assert.deepEqual(navigation.shortestDirectedPath('a', 'c'), ['a', 'c']);
  assert.deepEqual(navigation.shortestDirectedPath('c', 'a'), []);
});
