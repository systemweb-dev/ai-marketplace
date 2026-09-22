# Evolucao incremental da sw-flow-diagram - Implementation Plan

> **Execucao:** Implementar este plano task-by-task. Steps usam checkbox (`- [x]`) para tracking. Ver secao "Execution Handoff" da skill `sw-plan` para os 2 modos de execucao disponiveis.

**Goal:** Tornar a `sw-flow-diagram` mais segura, rápida de organizar e navegável em diagramas grandes, preservando o `flow.json` e o renderer atual.

**Architecture:** O contrato Python será validado antes do build e do save. O editor JavaScript passará a usar transações do modelo para histórico e dirty state; módulos separados cuidarão de layout, navegação, conectores e edição em lote. O servidor fará gravação por hash, build temporário e rename atômico.

**Tech Stack:** Python 3.11+, biblioteca padrão, Pytest, JavaScript standalone no HTML embutido, SVG, servidor `http.server` e Chromium opcional para exportação manual/headless.

**Tests:** Unitários apenas. Não criar integração ou E2E automatizados neste plano; a verificação manual do exemplo continua sendo obrigatória no checkpoint final.

---

## Arquivos e fronteiras

### Criar

- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/flow_contract.py`: contrato e validação canônica do documento.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/tests/test_flow_contract.py`: testes unitários do contrato.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/tests/test_serve_flow.py`: testes unitários das funções puras de save/hash/commit.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/editor/61-panel-actions.js`: edição em lote e validações visuais.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/editor/75-navigator.js`: minimap, outline, filtros e foco de caminho.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/editor/76-layout.js`: alinhamento, distribuição e auto-layout.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/editor/77-connectors.js`: offsets determinísticos, labels e feedback de edges.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/tests/editor-model.test.mjs`: testes unitários Node do estado transacional extraído do editor.

### Modificar

- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/build_flow.py`: validar antes do layout e remover descartes silenciosos.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/serve_flow.py`: hash, conflito, staging temporário e commit atômico.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/editor/10-model.js`: transações, revisões e API única de mutação.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/editor/40-render.js`: edges paralelas, estado filtrado e overlay de navegação.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/editor/50-interact.js`: mover seleção pela API do modelo.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/editor/60-panel.js`: integrar painel existente com ações em lote.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/editor/70-palettes.js`: adicionar nós pela API transacional.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/editor/90-main.js`: registrar ações, atalhos e save com revisão/hash.
- `plugins/sw-flow-diagram/skills/sw-flow-diagram/SKILL.md`: documentar organização, navegação, validação e conflitos.

## Fase 1: contrato, save e histórico

### Task 1: Extrair o contrato do flow.json

**Files:**
- Create: `scripts/flow_contract.py`
- Create: `tests/test_flow_contract.py`
- Modify: `scripts/build_flow.py:240-340`

- [x] **Step 1: Escrever testes unitários falhando**

Criar `test_flow_contract.py` com fixtures mínimas e AAA para:

```python
def test_accepts_request_http_shape():
    result = validate_flow(valid_flow())
    assert result == []

def test_rejects_duplicate_node_ids_with_path():
    flow = valid_flow()
    flow["nodes"].append({"id": "user", "label": "Outro"})
    errors = validate_flow(flow)
    assert {e["code"] for e in errors} == {"duplicate_id"}
    assert errors[0]["path"] == "nodes[1].id"

def test_rejects_missing_edge_endpoint_and_unknown_group():
    flow = valid_flow()
    flow["edges"] = [{"from": "missing", "to": "user"}]
    flow["nodes"][0]["group"] = "missing-group"
    codes = {e["code"] for e in validate_flow(flow)}
    assert codes == {"unknown_group", "unknown_edge_endpoint"}

def test_allows_reverse_edges_but_rejects_exact_duplicate():
    flow = valid_flow()
    flow["edges"] += [{"from": "user", "to": "api"}, {"from": "api", "to": "user"}]
    assert validate_flow(flow) == []
    flow["edges"].append({"from": "user", "to": "api"})
    assert any(e["code"] == "duplicate_edge" for e in validate_flow(flow))
```

Implement `valid_flow()` com os campos presentes no exemplo `examples/request-http/flow.json`.

- [x] **Step 2: Rodar os testes para confirmar a falha**

Run: `python3 -m unittest discover -s plugins/sw-flow-diagram/skills/sw-flow-diagram/tests -p "test_flow_contract.py"`

Expected: FAIL porque `flow_contract.py` ainda não existe.

- [x] **Step 3: Implementar o validador mínimo**

Em `flow_contract.py`, expor `validate_flow(flow) -> list[dict]` e `assert_valid_flow(flow) -> None`.
Usar erros com `code`, `path` e `message`; validar IDs com `^[a-z0-9][a-z0-9_-]{0,63}$`, labels,
notes, cores, grupos, endpoints, edges exatas, posições e enums conhecidos. Preservar campos
desconhecidos, mas nunca ignorar campos conhecidos inválidos.

Em `build_flow.py`, chamar `assert_valid_flow(F)` logo depois de carregar o JSON e antes de calcular
posições. Remover os caminhos que simplesmente pulam edges sem endpoint.

- [x] **Step 4: Rodar os testes para confirmar a passagem**

Run: `python3 -m unittest discover -s plugins/sw-flow-diagram/skills/sw-flow-diagram/tests -p "test_flow_contract.py"`

Expected: todos os testes PASS.

- [x] **Step 5: Verificar manualmente a fixture existente**

Run: `python3 plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/build_flow.py --dir plugins/sw-flow-diagram/skills/sw-flow-diagram/examples/request-http`

Expected: `flow.html` continua sendo gerado sem erro.

### Task 2: Tornar o save seguro e detectar conflitos

**Files:**
- Create: `tests/test_serve_flow.py`
- Modify: `scripts/serve_flow.py:1-78`

- [x] **Step 1: Escrever testes unitários falhando**

Testar funções puras que serão expostas por `serve_flow.py`:

```python
def test_sha256_changes_when_file_changes(tmp_path):
    path = tmp_path / "flow.json"
    path.write_text("{}", encoding="utf-8")
    first = file_sha256(path)
    path.write_text('{"title":"novo"}', encoding="utf-8")
    assert file_sha256(path) != first

def test_conflict_is_reported_before_staging(tmp_path):
    flow = tmp_path / "flow.json"
    flow.write_text('{"title":"atual"}', encoding="utf-8")
    result = save_candidate(tmp_path, {"title": "candidato"}, "hash-incorreto", build_fn=lambda _: None)
    assert result["status"] == 409
    assert flow.read_text(encoding="utf-8") == '{"title":"atual"}'

def test_failed_build_keeps_original_document(tmp_path):
    flow = tmp_path / "flow.json"
    flow.write_text('{"title":"funcional"}', encoding="utf-8")
    original_hash = file_sha256(flow)
    result = save_candidate(tmp_path, {"title": "invalido"}, original_hash,
                            build_fn=lambda _: (_ for _ in ()).throw(BuildError("falhou")))
    assert result["status"] == 500
    assert file_sha256(flow) == original_hash
```

- [x] **Step 2: Rodar os testes para confirmar a falha**

Run: `python3 -m unittest discover -s plugins/sw-flow-diagram/skills/sw-flow-diagram/tests -p "test_serve_flow.py"`

Expected: FAIL porque `file_sha256`, `save_candidate` e `BuildError` ainda não existem.

- [x] **Step 3: Implementar staging e commit atômico**

Adicionar `file_sha256(path)`, `BuildError`, `save_candidate(dirpath, data, expected_hash, build_fn)` e
`atomic_replace(path, staged_path)`. O candidato deve ser escrito em diretório temporário criado
com `tempfile.mkdtemp(dir=dirpath)`, validado, buildado nesse diretório e substituído somente após
sucesso. Usar `os.replace` para o JSON e o HTML; limpar o temporário em `finally`.

O handler deve aceitar `{"flow": ..., "baseHash": "..."}`, responder `409` para hash divergente,
`400` para JSON/contrato inválido e `500` para falha de build, sempre com `{ok, code, message}`.

- [x] **Step 4: Rodar os testes para confirmar a passagem**

Run: `python3 -m unittest discover -s plugins/sw-flow-diagram/skills/sw-flow-diagram/tests -p "test_serve_flow.py"`

Expected: todos os testes PASS.

### Task 3: Centralizar transações, revisões e dirty state

**Files:**
- Create: `tests/editor-model.test.mjs`
- Modify: `scripts/editor/10-model.js:1-112`
- Modify: `scripts/editor/50-interact.js`, `60-panel.js`, `70-palettes.js`, `90-main.js`

- [x] **Step 1: Extrair funções puras de estado**

Criar uma unidade browser/Node sem DOM com `createHistory()`, `transact(state, mutation)`,
`undo(state)`, `redo(state)`, `markSaved(state)` e `isDirty(state)`. Cada mutação, undo e redo
gera revisão monotônica; `isDirty` compara `modelRevision` e `savedRevision`.

- [x] **Step 2: Escrever testes unitários Node**

Em `editor-model.test.mjs`, usar `node --test` para cobrir: uma transação por operação, undo/redo,
undo depois de save, redo limpando o futuro, operação em lote como uma entrada e restauração de
nodes/edges/groups/posições.

- [x] **Step 3: Rodar os testes para confirmar a falha**

Run: `node --test plugins/sw-flow-diagram/skills/sw-flow-diagram/tests/editor-model.test.mjs`

Expected: FAIL antes da extração da unidade testável.

- [x] **Step 4: Adaptar o editor às transações**

Fazer `addNode`, edição de label, movimento, conexão, relink, exclusão, duplicação, mudança de
grupo e futuras ações de layout chamarem a API transacional. Remover mutações diretas fora do modelo.
Salvar deve chamar `markSaved` somente depois de resposta HTTP 200. Recalcular `dirty` após undo/redo.

- [x] **Step 5: Rodar os testes unitários**

Run: `node --test plugins/sw-flow-diagram/skills/sw-flow-diagram/tests/editor-model.test.mjs`

Expected: todos os testes PASS.

## Fase 2: organização e navegação

### Task 4: Adicionar alinhamento, distribuição e auto-layout

**Files:**
- Create: `scripts/editor/76-layout.js`
- Modify: `scripts/editor/10-model.js`, `90-main.js`, `build_flow.py`
- Modify: `tests/editor-model.test.mjs`

- [x] **Step 1: Implementar operações puras de geometria**

Expor `alignNodes(ids, axis, edge)`, `distributeNodes(ids, axis)` e `autoLayout(flow, direction)`.
Usar ordenação estável por grupo e ID, camadas derivadas das edges e espaçamento já usado pelo
renderer. `autoLayout` recalcula todas as posições, mantém grupos planos, coloca nós sem grupo em
camada própria e ignora grupos vazios.

- [x] **Step 2: Adicionar testes unitários de geometria**

Cobrir alinhamento em cada borda, distribuição uniforme, grafo com ramificação, ciclo, nó sem grupo,
grupo vazio e determinismo: duas chamadas com o mesmo JSON devem produzir posições idênticas.

- [x] **Step 3: Integrar ações como transações únicas**

Adicionar botões e atalhos no `90-main.js`. Organizar e cada operação de seleção devem gerar uma
entrada única de undo e atualizar o render sem escrever estado de sessão no JSON.

- [x] **Step 4: Rodar testes unitários e build da fixture**

Run: `node --test plugins/sw-flow-diagram/skills/sw-flow-diagram/tests/editor-model.test.mjs`

Expected: testes de geometria PASS.

Run: `python3 plugins/sw-flow-diagram/skills/sw-flow-diagram/scripts/build_flow.py --dir plugins/sw-flow-diagram/skills/sw-flow-diagram/examples/request-http`

Expected: HTML gerado e sem erro de validação.

### Task 5: Adicionar minimap, outline, filtros e foco de caminho

**Files:**
- Create: `scripts/editor/75-navigator.js`
- Modify: `scripts/editor/40-render.js`, `90-main.js`
- Modify: `scripts/editor/00-util.js` e estilos embutidos no template de `build_flow.py`

- [x] **Step 1: Implementar consultas puras**

Expor `visibleNodes(flow, session)`, `shortestDirectedPath(flow, from, to)` e `outline(flow)`.
O caminho deve escolher o menor caminho dirigido e, em empate, a sequência lexicograficamente menor.
Filtros apenas ocultam/diminuem; nunca removem elementos do documento.

- [x] **Step 2: Adicionar testes unitários Node**

Cobrir caminho inexistente, ramificação, ciclo, empate determinístico, nó em grupo recolhido e
filtro que não altera a lista original de nodes/edges.

- [x] **Step 3: Integrar UI de sessão**

Adicionar minimap clicável, outline plano grupo → nós, contadores de visíveis/ocultos, filtros por
texto/grupo/ícone e seletores de origem/destino. O foco abre grupo recolhido, seleciona o caminho e
esmaece o restante; estado fica em memória e não é salvo no JSON.

- [x] **Step 4: Verificar manualmente o exemplo aberto**

Abrir `http://127.0.0.1:8900/flow.html`, criar um filtro, focar `user` → `db`, recolher `app`, usar
o minimap e confirmar que o JSON não ganhou campos de sessão.

## Fase 3: edição, conectores e UX

### Task 6: Edição em lote e conectores legíveis

**Files:**
- Create: `scripts/editor/61-panel-actions.js`, `scripts/editor/77-connectors.js`
- Modify: `scripts/editor/40-render.js`, `60-panel.js`, `90-main.js`
- Modify: `tests/editor-model.test.mjs`

- [x] **Step 1: Implementar ações de seleção em lote**

Adicionar mudança de grupo, shape, ícone, estilo e animação para todos os nós/edges compatíveis.
Uma ação deve usar uma transação e atualizar o painel com a quantidade afetada.

- [x] **Step 2: Implementar edges paralelas e feedback**

Calcular offset estável por par de endpoints e índice de edge; reposicionar label junto da geometria.
Manter `fromSide`/`toSide` e não adicionar waypoints ao JSON nesta fase. Ao recolher grupo, exibir
contador de edges fundidas e abrir o grupo correto quando uma edge agregada for selecionada.

- [x] **Step 3: Adicionar testes unitários**

Cobrir atualização em lote atômica, exclusão com edges dependentes, offsets determinísticos para
edges paralelas e preservação de edges reversas.

- [x] **Step 4: Verificar manualmente edição e undo**

No navegador, selecionar múltiplos nós, editar grupo/shape, criar e religar edges, recolher grupo,
desfazer e refazer. Confirmar que cada ação volta em uma etapa.

### Task 7: Acessibilidade, responsividade e fluxo da skill

**Files:**
- Modify: `scripts/build_flow.py` template HTML/CSS/toolbar
- Modify: `scripts/editor/65-dock.js`, `60-panel.js`, `90-main.js`
- Modify: `skills/sw-flow-diagram/SKILL.md`

- [x] **Step 1: Ajustar controles acessíveis**

Adicionar `aria-label` aos botões, foco visível, ordem de teclado para toolbar/painel/paleta, anúncio
textual de erros de validação e alternativa que não dependa somente de cor ou ícone.

- [x] **Step 2: Ajustar telas estreitas**

Em largura menor que 900px, transformar dock e painel em áreas recolhíveis; em largura menor que
640px, manter apenas um painel aberto por vez e não bloquear o canvas.

- [x] **Step 3: Atualizar instruções da skill**

Documentar Organizar, minimap, outline, filtros, foco de caminho, conflitos `409`, limites do MVP
e o comportamento opcional de abrir `http://127.0.0.1:<port>/flow.html` com fallback para exibir a URL.

- [x] **Step 4: Verificar manualmente o fluxo completo**

Usar a fixture `request-http`: build, abrir no servidor local, editar, organizar, navegar, salvar,
recarregar e exportar SVG/PNG pela toolbar. Se Chromium estiver disponível, executar também o comando
de exportação headless; caso contrário, registrar o fallback manual.

> **Execução:** tasks 1 a 5 saíram na sessão anterior (OpenCode, com revisão por subagente a
> cada lote); tasks 6 e 7 e a verificação final foram feitas em 2026-09-22, com os testes, a
> varredura de segredos e o smoke manual rodados de novo do zero.

## Verificação final

- [x] Rodar `python3 -m unittest discover -s plugins/sw-flow-diagram/skills/sw-flow-diagram/tests -p "test_*.py"`.
- [x] Rodar `node --test plugins/sw-flow-diagram/skills/sw-flow-diagram/tests/editor-model.test.mjs`.
- [x] Rodar `python3 scripts/scan_secrets.py paths plugins/sw-flow-diagram docs/specs/2026-09-21-evolucao-incremental-da-sw-flow-diagram`.
- [x] Fazer o smoke manual no exemplo `request-http` e confirmar que não há dados de sessão no `flow.json`.
- [x] Atualizar `CHANGELOG.md` com a versão da skill após a implementação e sincronização.

## Gaps assumidos

- Como o usuário escolheu somente testes unitários, save HTTP, build, export e browser não terão
  testes automatizados neste plano; serão verificados manualmente.
- O projeto não possui manifesto de dependências nem runner JavaScript configurado. O plano usa
  `node --test` nativo e Pytest já presente no ambiente, sem introduzir framework de teste.
- A criação assistida continua sendo responsabilidade do fluxo da skill e não um agente embutido no
  HTML; o editor apenas fornece ações determinísticas.
