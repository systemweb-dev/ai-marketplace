/* ---- seleção (um ou vários) ---- */
const sel = { nodes: new Set(), edge: null };   // edge = índice, ou null

const hasSel = () => sel.nodes.size > 0 || sel.edge !== null;
const selNodeIds = () => [...sel.nodes];
function clearSel() { sel.nodes.clear(); sel.edge = null; }
function selectNode(id, additive) {
  if (!additive) { sel.nodes.clear(); sel.edge = null; }
  if (additive && sel.nodes.has(id)) sel.nodes.delete(id); else sel.nodes.add(id);
}
function selectEdge(i) { sel.nodes.clear(); sel.edge = i; }
const isNodeSelected = id => sel.nodes.has(id);
