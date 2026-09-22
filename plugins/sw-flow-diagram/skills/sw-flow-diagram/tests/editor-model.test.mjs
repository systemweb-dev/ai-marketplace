import test from 'node:test';
import assert from 'node:assert/strict';
import state from '../scripts/editor/05-state.js';
const { begin, createHistory, isDirty, markSaved, redo, transact, undo } = state;

test('uma transacao cria uma revisao e limpa o futuro', () => {
  const history = createHistory({ nodes: [] });
  transact(history, state => ({ ...state, nodes: ['a'] }));

  assert.deepEqual(history.current.nodes, ['a']);
  assert.equal(history.revision, 1);
  assert.equal(isDirty(history), true);
});

test('undo e redo preservam o estado e geram novas revisoes', () => {
  const history = createHistory({ nodes: [] });
  transact(history, state => ({ ...state, nodes: ['a'] }));
  transact(history, state => ({ ...state, nodes: ['a', 'b'] }));

  assert.equal(undo(history), true);
  assert.deepEqual(history.current.nodes, ['a']);
  assert.equal(redo(history), true);
  assert.deepEqual(history.current.nodes, ['a', 'b']);
  assert.equal(history.revision, 4);
});

test('undo depois de salvar marca o documento como sujo', () => {
  const history = createHistory({ nodes: [] });
  transact(history, state => ({ ...state, nodes: ['a'] }));
  markSaved(history);

  assert.equal(isDirty(history), false);
  undo(history);
  assert.equal(isDirty(history), true);
});

test('uma operacao em lote e uma unica transacao', () => {
  const history = createHistory({ nodes: [] });
  transact(history, state => ({ ...state, nodes: ['a', 'b', 'c'] }));

  assert.equal(history.past.length, 1);
  assert.equal(undo(history), true);
  assert.deepEqual(history.current.nodes, []);
});

test('begin registra o snapshot antes de uma mutacao externa', () => {
  const history = createHistory(null);
  begin(history, { nodes: [] });
  history.current = { nodes: ['a'] };

  assert.equal(undo(history), true);
  assert.deepEqual(history.current, { nodes: [] });
});
