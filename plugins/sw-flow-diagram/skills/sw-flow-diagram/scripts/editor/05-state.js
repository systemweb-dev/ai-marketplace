/* Núcleo de histórico compartilhado pelo bundle e pelos testes Node. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.FlowState = factory();
})(typeof globalThis === 'object' ? globalThis : this, function () {
  function clone(value) { return structuredClone(value); }
  function createHistory(initial, max) {
    return { current: clone(initial), past: [], future: [], revision: 0, savedRevision: 0, max: max || 60 };
  }
  function transact(history, mutation) {
    history.past.push(clone(history.current));
    if (history.past.length > history.max) history.past.shift();
    history.current = mutation(clone(history.current)); history.future.length = 0; history.revision += 1;
    return history.current;
  }
  function begin(history, current) {
    history.current = clone(current);
    history.past.push(clone(current));
    if (history.past.length > history.max) history.past.shift();
    history.future.length = 0; history.revision += 1;
  }
  function undo(history) {
    if (!history.past.length) return false;
    history.future.push(clone(history.current)); history.current = history.past.pop(); history.revision += 1; return true;
  }
  function redo(history) {
    if (!history.future.length) return false;
    history.past.push(clone(history.current)); history.current = history.future.pop(); history.revision += 1; return true;
  }
  function markSaved(history) { history.savedRevision = history.revision; }
  function isDirty(history) { return history.revision !== history.savedRevision; }
  return { createHistory, transact, begin, undo, redo, markSaved, isDirty };
});
