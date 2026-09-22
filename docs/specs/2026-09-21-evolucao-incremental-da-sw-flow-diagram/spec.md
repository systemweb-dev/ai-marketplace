---
titulo: Evolucao incremental da sw-flow-diagram
slug: 2026-09-21-evolucao-incremental-da-sw-flow-diagram
criado: 2026-09-21
estado: concluido
---

# Evolucao incremental da sw-flow-diagram

> Dossiê deste trabalho. `spec.md` é a fonte da verdade do design; `plan.md` é o passo a
> passo de execução; `referencias/` guarda o material de apoio (prints, PDFs, diagramas).

## Exploração & decisões

### Problema

A `sw-flow-diagram` já cria e edita diagramas funcionais, mas exige trabalho manual demais
para criar uma versão legível e perde eficiência quando o diagrama cresce.

### Ângulos levantados

- criação assistida a partir de descrição e revisão de legibilidade;
- edição profissional com alinhamento, distribuição, edição em lote e conectores melhores;
- escala com minimap, estrutura, filtros e foco em caminhos;
- reescrita completa do editor, considerada desnecessária para este ciclo.

### Suposições confirmadas e derrubadas

- `flow.json` continuará sendo a fonte da verdade;
- o renderer SVG atual será preservado e evoluído pontualmente;
- o canvas deve permanecer determinístico; a assistência fica no fluxo da skill;
- grupos continuam planos no MVP, não haverá subgrupos;
- waypoints persistentes de conectores ficam fora do MVP;
- salvar e recarregar não pode descartar alterações locais nem aceitar dados semanticamente inválidos.

### Direção escolhida

Evolução incremental sobre o modelo e o renderer atuais. A menor solução que resolve o problema
é adicionar validação, transações de mutação, organização, navegação e edição em lote sem criar
um novo formato de documento ou uma camada de colaboração.

## Objetivo & outcome

Permitir que uma pessoa crie, organize, edite e apresente diagramas pequenos ou grandes com menos
ajuste manual e sem perder alterações. O resultado deve ser verificável por fixtures de fluxo,
operações de editor e round-trip de save/reload.

## Não-objetivos

- colaboração multiusuário ou sincronização remota;
- banco de dados, autenticação ou workspace persistente;
- edição livre de imagens, desenho à mão ou texto solto;
- subgrupos aninhados;
- waypoints manuais persistidos para edges;
- reescrita completa do renderer;
- geração automática de código de arquitetura.

## Restrição de simplicidade

Manter o `flow.json`, o build embutido e o servidor local existentes. Não criar um novo framework
de estado nem um novo formato de diagrama. Toda mutação deve passar por uma API pequena do modelo;
recursos de apresentação e sessão não devem ser gravados no JSON sem necessidade.

## Appetite e fases de entrega

O trabalho será executado em três fases independentes. Cada fase deve deixar o editor utilizável e
ser verificável sem depender da fase seguinte.

### Fase 1: contrato e segurança do editor

- validador único compartilhado por build e save;
- save com build temporário e substituição atômica;
- revisão salva em vez de booleano `dirty`;
- API transacional para mutações e operações em lote;
- testes de round-trip, conflito e falha de build.

### Fase 2: organização e navegação

- alinhamento, distribuição e auto-layout determinístico;
- minimap, outline plano de grupos/nós e filtros de sessão;
- foco de caminho com comportamento definido para ciclos;
- fixture grande e smoke test de navegação.

### Fase 3: edição e UX

- edição em lote e feedback de conexão;
- acessibilidade, responsividade e exportação;
- integração da criação assistida no fluxo da skill.

### Depois do MVP

- roteamento com waypoints persistentes;
- grupos aninhados e subdiagramas;
- colaboração, histórico remoto e controle de concorrência entre máquinas;
- biblioteca avançada de templates e importação de formatos externos.

## Arquitetura

Preservar `scripts/editor/` e separar responsabilidades:

- `10-model.js`: estado do documento, transações, histórico, revisões e operações de mutação;
- `layout.js`: alinhamento, distribuição e auto-layout determinístico;
- `navigator.js`: minimap, outline, filtros, contadores e foco de caminho;
- `connectors.js`: feedback de ligação, edges paralelas e labels, sem waypoints no MVP;
- `61-panel-actions.js`: edição em lote e validações visuais, mantendo `60-panel.js` como painel existente;
- `90-main.js`: atalhos e composição dos módulos, sem lógica de domínio.

O build deve manter uma ordem explícita de bundle. O novo módulo de painel não pode depender de
um nome ambíguo ou de ordenação acidental de arquivos.

## Contrato de dados e validação

O contrato canônico será um arquivo de schema versionado ao lado de `build_flow.py`. A validação
canônica roda em Python antes do build e do save; o editor JavaScript faz apenas pré-validação para
feedback imediato e usa os mesmos códigos e caminhos de erro. Não será adicionada uma dependência
de JSON Schema no MVP.

O validador rejeita, com erro estruturado `{code, path, message}`:

- IDs vazios ou duplicados;
- referências de `from`, `to` ou `group` inexistentes;
- edges duplicadas com o mesmo `from` e `to`; edges reversas são permitidas;
- posições que não sejam pares numéricos finitos;
- enums desconhecidos para layout, direção, shape, estilo e animação;
- IDs fora de `^[a-z0-9][a-z0-9_-]{0,63}$`;
- labels vazios ou maiores que 160 caracteres, notes maiores que 2000 caracteres;
- cores fora de `#[0-9a-fA-F]{6}` quando informadas.

Campos desconhecidos são preservados para compatibilidade futura, mas campos conhecidos com enum
inválido falham. O build retorna código não zero e não gera HTML quando a validação falha.

O build não pode descartar silenciosamente edges inválidas. O round-trip deve preservar campos
permitidos e a fixture existente `request-http` deve continuar válida.

## Save, reload e histórico

O editor envia no `POST /save` o documento candidato e o hash SHA-256 do `flow.json` que estava
aberto. O servidor compara esse hash com o arquivo atual e responde `409` em conflito, sem escrever.
Para uma gravação aceita, o servidor cria um diretório temporário no mesmo diretório do fluxo,
valida o candidato, gera o HTML ali, sincroniza o arquivo temporário e substitui o JSON via rename
atômico. O HTML só substitui o anterior depois que o JSON candidato foi validado e buildado. Em
qualquer falha, o documento e o HTML anteriores permanecem intactos; a resposta inclui código e
mensagem estruturada. Backups não fazem parte do MVP, pois o histórico Git é a recuperação oficial.

No editor, cada transação, undo e redo gera uma nova revisão monotônica. `savedRevision` recebe a
revisão efetivamente persistida; `dirty` é sempre `modelRevision !== savedRevision`. Auto-layout,
edição assistida e operações em lote resultam em uma única entrada de histórico. Um save com resposta
`409` mantém o estado local e oferece recarregar ou exportar uma cópia com sufixo `-conflict`.

Se o live-reload detectar alteração externa enquanto existem alterações locais, deve bloquear o
reload automático e oferecer manter, recarregar ou salvar uma cópia. O assistente da skill deve
aplicar mudanças como um modelo validado ou patch transacional, não editar o arquivo por um caminho
paralelo sem coordenação com o editor aberto.

## Layout e navegação

Alinhamento e distribuição operam na seleção visível e não alteram nós ocultos. A ação Organizar
recalcula todos os nós usando layout em camadas, ordenação estável por `group` e depois `id`,
preservando grupos planos, tratando nós sem grupo em uma camada própria e ignorando grupos vazios.
Organizar substitui todas as posições manuais; mover um nó depois disso cria uma nova posição manual.
Um nó novo recebe posição local e não dispara auto-layout. A ação é determinística e desfeita em uma
única operação.

O estado de minimap, câmera, seleção, filtros e grupos recolhidos é estado de sessão. Não entra no
`flow.json`, salvo se uma necessidade concreta surgir. O outline é plano: grupos com seus nós e nós
sem grupo. O minimap deve permitir clicar para mover a viewport.

Filtros não devem apagar dados: apenas ocultam elementos e indicam quantos estão ocultos. O foco de
caminho oferece dois seletores de origem e destino; ambos são obrigatórios. Calcula o caminho dirigido
mais curto; em empate, escolhe a sequência lexicograficamente menor por ID. Se não houver caminho,
mantém a seleção e mostra uma mensagem. Filtros e grupos recolhidos não alteram o cálculo: elementos
fora do caminho ficam esmaecidos e o ciclo alcançável é marcado visualmente.

## Conectores e edição

No MVP, conectores ganham offsets determinísticos para edges paralelas, labels posicionados de forma
legível e feedback claro durante criação/religação. O resultado precisa sobreviver a build, reload e
exportação. Waypoints persistidos não fazem parte desta entrega.

O painel permite editar em lote apenas propriedades compatíveis. Exclusões de nós, grupos, edges e
operações assistidas que removam múltiplos elementos devem ter confirmação; undo continua sendo a
segunda proteção. Acessibilidade inclui foco de teclado, `aria-label`, alternativa textual para
cores/ícones e controles navegáveis sem mouse. Em telas estreitas, dock e painel devem virar áreas
recolhíveis, sem bloquear o canvas.

## Fluxo da skill

Ao interpretar uma descrição, a skill deve sugerir layout, direção, agrupamentos e modo de saída.
Após gerar, deve validar o documento e apontar problemas de legibilidade. Se o resultado for denso,
deve oferecer organização automática ou separação em diagramas. O servidor de edição local deve ser
iniciado e o link aberto no navegador quando o ambiente permitir.

## Testes e fitness functions

- O build deve rejeitar IDs duplicados, referências quebradas, grupos inexistentes e posições inválidas.
- Um save inválido, conflito ou build com erro não pode alterar o `flow.json` nem o HTML anterior.
- Toda mutação de documento deve produzir exatamente uma transação de undo; undo após save deve marcar o documento como sujo.
- Auto-layout da mesma fixture deve gerar as mesmas posições e não perder grupos ou edges.
- A fixture atual deve abrir, adicionar, mover, conectar, religar, filtrar, organizar, salvar, recarregar e exportar sem erro.
- Uma fixture de 100 nós deve renderizar em até 500 ms em execução headless de referência; uma de 500 nós deve renderizar em até 2 s.
- O smoke test deve confirmar que todos os controles principais são alcançáveis por teclado e têm `aria-label`.
- O export SVG/PNG deve refletir conectores e labels sem overlays de edição.

O ambiente mínimo de teste é Python 3.11+, Pytest e Chromium opcional. Chromium é obrigatório
somente para exportação headless e smoke browser; sem ele, os testes de contrato, servidor e build
continuam obrigatórios e o fallback de exportação pela toolbar deve ser documentado.

## Decisões estruturais

### Documento atual em vez de novo formato

**Contexto:** o `flow.json` é versionável e já é a fonte da verdade.

**Decisão:** evoluir o contrato somente quando uma capacidade exigir persistência.

**Alternativas descartadas:** migrar para banco ou reescrever o modelo.

**Consequências:** menor risco de migração, com necessidade de validar campos e manter compatibilidade.

### Transações no modelo

**Contexto:** módulos atuais alteram estado diretamente.

**Decisão:** centralizar mutações em API transacional do modelo.

**Alternativas descartadas:** cada módulo implementar seu próprio undo.

**Consequências:** histórico e dirty state ficam consistentes, mas operações antigas precisam ser adaptadas.

### Conectores sem waypoints no MVP

**Contexto:** o renderer atual calcula edges a partir de endpoints e lados.

**Decisão:** melhorar paralelas, labels e feedback sem persistir rotas manuais.

**Alternativas descartadas:** introduzir waypoints agora.

**Consequências:** entrega menor e exportável, mas diagramas muito densos ainda terão limites conhecidos.

## Fora deste spec

Este documento define o design. A decomposição em arquivos, comandos, ordem de implementação e
testes concretos deve ser registrada posteriormente no `plan.md`, após aprovação deste spec.
