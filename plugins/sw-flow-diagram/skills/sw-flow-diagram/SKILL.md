---
name: sw-flow-diagram
description: >
  Monta diagramas de fluxo/arquitetura visuais a partir de uma descrição em linguagem natural —
  pra apresentação, explicação ou documentação. Genérica para QUALQUER fluxo (arquitetura web,
  pipeline de dados, jornada de usuário, processo de negócio): você descreve "request → Cloudflare
  → load balancer → servidores → banco" e sai um diagrama bonito, com ícones, animado (o request
  percorrendo o caminho) e exportável. Motor próprio em HTML/SVG (não Mermaid/D2): gera um flow.json
  editável + renderiza HTML standalone com live-reload no navegador. Use SEMPRE que o usuário quiser
  desenhar/visualizar um fluxo ou arquitetura — "monta um diagrama de fluxo", "desenha a arquitetura",
  "diagrama do request passando por X, Y, Z", "fluxograma pra apresentação", "como o pedido percorre
  o sistema", "mostra o caminho dos dados", "diagrama de microserviços", "cria um fluxo visual de A→B→C".
  Dispare mesmo sem a palavra "diagrama" — basta a intenção de visualizar como as coisas se conectam/fluem.
  Editor de canvas completo: paleta lateral que se ARRASTA pro diagrama, formas de fluxograma
  (decisão, processo, banco, documento, início/fim…), multi-seleção, desfazer/refazer, painel de
  propriedades, guias de alinhamento, busca, grupos recolhíveis e modo apresentação passo-a-passo —
  serve tanto pra 5 caixas quanto pra um diagrama grande de processo de negócio. NÃO é um editor de
  imagem livre/desenho gráfico, não gera código de verdade de uma arquitetura, nem revisa/analisa
  código. Interação e saída em PT-BR.
---

# Flow Diagram

Transformar a descrição de um caminho ("request → Cloudflare → load balancer → servidores → banco") em um **diagrama visual, animado e exportável**, no padrão visual das skills do usuário (HTML/SVG próprio, light/dark, live-reload). A fonte da verdade é um **`flow.json`** editável; um script renderiza pra HTML.

É **genérica**: o exemplo é de infra, mas serve pra qualquer fluxo — pipeline de dados, jornada de usuário, processo de negócio, máquina de estados.

## Como funciona (visão geral)

`descrição em linguagem natural → flow.json → build_flow.py → flow.html (servido com live-reload) → itera → exporta`

## Regra das perguntas

Toda **decisão** ao usuário (modo de saída, qual layout quando ambíguo, "aplica/ajusta") usa `AskUserQuestion` (menu clicável) — nunca texto solto, nunca termine turno com pergunta em texto. A **descrição livre do fluxo e os ajustes** ("adiciona um cache antes do banco") são o usuário dirigindo — não force menu aí.

## Workflow

### 1. Interpretar o cenário

Da descrição da pessoa, extraia:
- **Nós** (caixas): cada componente/etapa. Dê um `id` curto, um `label` legível e um **ícone** que ajude a reconhecer (veja a lista de ícones).
- **Arestas** (setas): quem conecta com quem; `label` opcional (protocolo, porta, condição: "443", "miss", "async").
- **Grupos**: agrupamentos lógicos (Edge, Aplicação, Dados…) — viram caixas (no layout `flow`) ou faixas (no `tiers`).

### 2. Escolher o layout

- **`flow`** — esquerda→direita por estágios, com ramificação (um nó abre em vários) e grupos em caixa. Padrão pra "caminho do request". Cobre a maioria.
- **`tiers`** — faixas horizontais por grupo (Edge · App · Dados…). Bom pra arquitetura em camadas.
- **`graph`** — grafo com mais ligações/ciclos (microserviços conversando). Usa o mesmo layout em camadas, tolerando arestas de volta.

**Direção** (`"direction"`): `"LR"` (esquerda→direita, padrão) ou `"TB"` (cima→baixo). TB vale pra
`flow`/`graph` (o `tiers` é sempre em faixas horizontais). Use TB pra fluxogramas/decisões verticais
e pra caber em tela alta (slide retrato); LR pra "caminho do request" e telas largas.

Infira pelo cenário; se ficar ambíguo, **pergunte via `AskUserQuestion`**.

### 3. Perguntar o modo de saída (`AskUserQuestion`)

- **Animado ao vivo** → `animation.mode: "packet"` (bolinha percorrendo as arestas) e arestas `animated:true`. Pra apresentar.
- **Estático** → `animation.mode: "none"`. Pronto pra exportar SVG/PNG pro slide.
- **Ambos** → gere animado; a toolbar do HTML já exporta a versão estática (botões SVG/PNG).
- **Explicativo** → preencha `note` em cada nó relevante (aparece como tooltip ao passar o mouse) e use labels nas arestas. Foco em entender cada parte.

(Outras animações: `highlight` = nós acendem em sequência; `draw` = entra desenhando.)

### 4. Gerar e servir

- Escreva o **`flow.json`** em `./flows/<slug>/flow.json` (slug do título em minúsculas com hífens). Schema completo no topo de `scripts/build_flow.py`.
- Rode: `python3 ~/.claude/skills/sw-flow-diagram/scripts/build_flow.py --dir ./flows/<slug>` → gera `flow.html`.
- **Sirva com live-reload + edição** (uma vez por sessão): `python3 ~/.claude/skills/sw-flow-diagram/scripts/serve_flow.py --dir ./flows/<slug> --port 8900` em background, e passe `http://127.0.0.1:8900/flow.html`. Esse servidor (no lugar do `http.server` comum) habilita a **edição no canvas** (mover/adicionar/conectar/religar/excluir — ver passo 5) — ele aceita `POST /save`, que grava o `flow.json` e re-roda o build; a página recarrega sozinha. (Se só quiser visualizar sem editar, `python3 -m http.server` também serve, mas a edição não salva.) O editor vive em `scripts/editor/*.js` e é **embutido** no `flow.html` pelo build — o HTML gerado é um arquivo único, que funciona até aberto direto do disco.

### 5. Iterar — dois jeitos (os dois atualizam na hora)

- **Pelo chat:** a pessoa pede ajustes em linguagem natural ("o LB ramifica em 4 servidores", "põe um WAF antes do Cloudflare", "muda o accent pra verde"). **Você edita o `flow.json`** e roda o build — a página recarrega sozinha.
- **No canvas, direto no navegador** (com `serve_flow.py`):

  **Adicionar**
  - **Paleta lateral:** arraste um item (forma ou componente) da coluna da esquerda pro diagrama.
    Soltou dentro de um grupo, o nó já nasce nele. Clique fora do canvas cancela.
  - **Duplo-clique no vazio:** abre a paleta com busca, no ponto do clique.
  - **Ctrl+D** duplica a seleção (as conexões internas à seleção vêm junto).

  **Selecionar e mover**
  - Clique num nó; **Shift+clique** soma à seleção; **Shift+arraste no fundo** faz laço.
  - **Ctrl+A** seleciona tudo. Arrastar qualquer selecionado move **todos** juntos.
  - **Guias magenta** aparecem ao arrastar e encaixam o nó com os vizinhos.
  - **Setas** movem 1px (10px com Shift).

  **Conectar**
  - Cada nó tem **4 portas** (cima, baixo, esquerda, direita) — aparecem ao passar o mouse.
    Arraste de qualquer uma até outro nó; a seta encosta no lado mais próximo do ponto onde
    você soltou, e o lado fica gravado (`fromSide`/`toSide`).
  - Clique numa seta e arraste a ponta pra religar noutro nó/lado.

  **Editar**
  - **Painel da direita** (abre ao selecionar): rótulo, **formato**, ícone, grupo, nota; na seta,
    rótulo, traço, animação e inverter sentido.
  - **Em lote:** com vários nós selecionados, o painel aplica **grupo, formato e ícone** a todos
    de uma vez e, para as **conexões internas à seleção** (as duas pontas selecionadas), traço e
    animação. O painel diz quantos itens a ação pegou, e **um Ctrl+Z desfaz o lote inteiro**.
  - **Duplo-clique** no nó ou na seta edita o rótulo no lugar.
  - **Delete** exclui a seleção (nó leva junto as conexões).
  - **Ctrl+Z / Ctrl+Shift+Z** desfazem e refazem qualquer uma dessas ações.

  **Organizar**
  - **Organizar** refaz o layout do diagrama inteiro em camadas, de forma determinística: o
    mesmo `flow.json` sempre cai no mesmo desenho.
  - **Alinhar** e **Distribuir** valem para a seleção (2 e 3 nós, no mínimo). Cada ação é uma
    transação: desfaz de uma vez.

  **Navegar em diagrama grande**
  - **Navegar** abre o minimapa com a estrutura do diagrama, o filtro por grupo e o **foco de
    caminho**: escolhidos dois nós, o editor acende o menor caminho dirigido entre eles e apaga
    o resto. Caminho que só existiria indo contra a seta não é inventado.
  - **Ctrl+F** busca o nó pelo nome e voa até ele (abre o grupo se estiver recolhido).
  - **Recolher grupo:** o **−** ao lado do nome do grupo vira uma caixa única; as setas que
    cruzavam a fronteira se religam à caixa, e a que representa várias mostra o número
    (`3 conexões`) para ninguém ler "só uma". Clique na caixa pra reabrir.
  - **Conexões paralelas** entre os mesmos dois nós (ida e volta, dois protocolos) abrem em
    leque, cada uma com o seu rótulo, em vez de se esconderem uma atrás da outra.
  - Roda = zoom, arrastar o fundo = pan, **0** enquadra, **+/−** ajustam o zoom.

  **Apresentar**
  - **▶ Apresentar** percorre o diagrama por etapas (ordem topológica): cada passo acende o
    trecho alcançado e escurece o resto, com a câmera acompanhando. **← →** ou espaço navegam,
    **Esc** sai. `flow.html?present=1` já abre apresentando — útil pra deixar o link pronto.

  **Salvar**
  - **Salvar** (ou **Ctrl+S**) grava no `flow.json`, incluindo as posições (`pos:[x,y]`).
    **⤢ Auto** apaga as posições e volta pro layout automático. O `flow.json` segue sendo a
    **fonte da verdade**. Com alterações pendentes o botão diz **"Salvar alterações"**, e sair
    sem salvar pede confirmação.
  - **Conflito (409):** se o `flow.json` mudou fora do editor desde que a página abriu, o
    servidor recusa a gravação e pergunta o que fazer: recarregar (descartando a edição local)
    ou **baixar `flow-conflict.json`** com o que estava na tela. Nada é sobrescrito em silêncio,
    e um documento inválido nunca substitui um válido: o build roda antes da troca, e a troca do
    `flow.json` e do `flow.html` é atômica.

  **Teclado e telas pequenas**
  - Todo botão da barra tem nome falado, o foco é visível e **cada nó é alcançável por Tab**
    (Enter seleciona, Shift+Enter soma à seleção). O resultado de salvar e os erros de validação
    são anunciados em texto, não só por cor.
  - Abaixo de 900px de largura, a paleta e o painel viram gavetas sobre o canvas; abaixo de
    640px, abrir o painel recolhe a paleta, para sempre sobrar diagrama na tela.

### 6. Exportar

A toolbar do `flow.html` exporta **SVG** e **PNG** (2×) com um clique. Pra **PNG@2x/3x ou PDF
headless** (sem abrir o navegador), rode:

```
python3 ~/.claude/skills/sw-flow-diagram/scripts/export_flow.py --dir ./flows/<slug> \
  --format both --scale 2 --theme light      # gera flow.png e flow.pdf no dir
```

Ele usa um Chrome/Chromium instalado (carrega o HTML com `?export=1` → sem toolbar, tamanho
justo, estático) e cai num aviso claro se não houver navegador (aí use o SVG/PNG da toolbar).

## Ícones disponíveis (use o nome no campo `icon`)

`user`, `server`, `database`, `storage`, `queue`, `cache`, `shield`, `cloud`, `balancer`,
`gateway`, `gear`, `service`, `document`, `message`, `mobile`, `browser`, `lock`, `clock`,
`decision`, `external`, `api`, `globe`, `proxy`, `cdn`, `firewall`, `function`, `container`,
`search`, `monitor`, `brain` (IA/modelo), `chat` (conversa/atendimento), `money` (pagamento),
`truck` (entrega/logística), `key` (chave/certificado), `flask` (teste/experimento),
`chart` (métrica/relatório), `team` (equipe/pessoas), `box` (genérico/fallback).

Escolha o que **comunica o papel** do nó (ex.: CDN/WAF → `shield`; fila → `queue`; serviço →
`service`; usuário/cliente → `user`; storage/bucket → `storage`). Se nada encaixar, use `box`
com um label claro. Conceito muito específico que mereça a logo real → o usuário pode apontar
um SVG/PNG e você embute (base64) — mas o padrão é o set genérico.

## Formas de fluxograma (campo `shape`)

Além do ícone, cada nó tem um **formato**. O padrão é `rounded` (processo). Os demais são o
vocabulário clássico de fluxograma — use-os quando o diagrama for de **processo/decisão**, não
de infraestrutura:

`rounded` (processo) · `rect` · `stadium` (início/fim) · `diamond` (**decisão**) ·
`parallel` (entrada/saída) · `cylinder` (banco de dados) · `circle` (conector) ·
`hexagon` (preparação) · `document` · `docs` (vários documentos) · `subroutine` (subprocesso) ·
`manual` (entrada manual) · `operation` (operação manual) · `delay` (espera) · `display` ·
`storage` · `merge` (junção) · `extract` (separação) · `offpage` (fora da página) ·
`cloud` (externo) · `note` (anotação).

Formas com rótulo **centralizado** (decisão, banco, conector…) não mostram ícone — o texto ocupa
o miolo. O rótulo é truncado ao que cabe na forma, então prefira nomes curtos num losango.

## Catálogo de componentes (blocos prontos)

O `build_flow.py` traz um **catálogo** (`CATALOG`) de blocos comuns já com label + ícone —
é o vocabulário pra montar o fluxo rápido, sem inventar. Categorias e itens:

São **148 componentes em 11 categorias** (a lista viva está em `CATALOG`, no
`scripts/build_flow.py`):

- **Cliente:** Usuário · Navegador · App Mobile · App Desktop · Terminal/PDV · Sistema externo ·
  Parceiro/SaaS · Dispositivo IoT · Chatbot · Atendente
- **Rede / Edge:** DNS · CDN · WAF · Firewall · Reverse Proxy · Load Balancer · API Gateway ·
  Ingress · Service Mesh · NAT · VPN · Rate Limiter · Edge Function · Proteção DDoS ·
  Terminação TLS · Bastion · VPC
- **Aplicação:** App Server · Front-end SPA · SSR · Microserviço · API · gRPC · WebSocket ·
  Function · Container · Worker · Job em lote · Orquestrador · Máquina de estados ·
  Motor de regras · Auth · Cron · Webhook · GraphQL · BFF · Feature Flag
- **Dados:** SQL · NoSQL · Grafos · Série temporal · Cache · Object Storage · Busca ·
  Data Warehouse · Data Lake · Vector DB · Read Replica · Session Store · ETL · CDC ·
  Backup · Migração
- **Mensageria:** Fila · Broker · Stream · E-mail · Notificação · Push · DLQ · Event Bus ·
  Pub/Sub · SMS · WhatsApp · Outbox · Retry
- **Segurança:** IdP · OAuth/OIDC · Secrets · KMS · Certificado · MFA · RBAC · Antivírus ·
  Zero Trust · Assinatura digital · Anonimização · SIEM
- **DevOps / Deploy:** Git · CI · CD · Build · Testes · Artifact Registry · Registro de
  imagens · Kubernetes · Serverless · IaC · Staging · Blue/Green · Canary · Rollback
- **IA / ML:** Modelo LLM · API de inferência · Embeddings · Pipeline RAG · Feature Store ·
  Model Registry · Treino/Fine-tuning · GPU Worker · Moderação/Guardrail · Avaliação
- **Integrações:** Gateway de pagamento · Pix · Boleto · Nota fiscal · Antifraude ·
  Transportadora · CRM · ERP · Analytics · Maps · Open Finance · Assinatura/SaaS
- **Observabilidade / Fluxo:** Monitoring · Métricas · Logs · Tracing · APM · Health check ·
  Alertas · Dashboard · Plantão · Auditoria · Scheduler · Decisão
- **Negócio / Processo:** Cliente · Equipe · Aprovação · Contrato · Proposta · Pedido ·
  Pagamento · Estoque · Entrega · Atendimento · Relatório · Prazo/SLA

A **paleta lateral** mostra tudo isso em categorias recolhíveis (a primeira já aberta, as
demais a um clique) com busca, e as formas de fluxograma em duas colunas. No canvas,
**duplo-clique numa área vazia abre a paleta do catálogo** (com busca) — escolhe o
componente e o nó já nasce com label + ícone certos ("+ Nó em branco" pra um genérico). Ao
interpretar a descrição da pessoa, mapeie os termos dela pra esses blocos (ex.: "balanceador"
→ Load Balancer/`balancer`, "proxy reverso" → Reverse Proxy/`proxy`, "gateway" → API
Gateway/`gateway`). Precisa de um bloco que não está no catálogo? É só criar o nó com um
`icon` do set e um label claro — o catálogo é atalho, não limite.

## Exemplos prontos (`examples/`)

Cinco diagramas completos, um de cada arranjo — abra qualquer um com o `serve_flow.py` para ver,
ou use como ponto de partida copiando o `flow.json`:

| Pasta | Arranjo | Serve para |
|---|---|---|
| `request-http` | `flow` · LR | caminho de um request pela infraestrutura |
| `aprovacao-de-despesa` | `flow` · **TB** | fluxograma clássico, com decisões em losango, espera, recusa e junção |
| `jornada-de-assinatura` | `flow` · **TB** | jornada do usuário em etapas, com grupos por fase e caminhos de recuperação |
| `camadas-saas` | `tiers` | arquitetura em faixas (cliente, borda, aplicação, dados, observabilidade) |
| `microservicos-pedido` | `graph` · LR | serviços conversando, com ida e volta entre os mesmos dois nós |

**Escolha o arranjo pelo formato da história, não por hábito:** processo com decisões e telas
altas pede **TB**; caminho de request e telas largas pedem **LR**; arquitetura em camadas pede
`tiers`; serviço que responde para quem chamou pede `graph`.

## flow.json — formato resumido

```json
{
  "title": "Request HTTP",
  "layout": "flow",
  "accent": "#2f6bf0",
  "animation": { "mode": "packet", "speed": 1 },
  "groups": [ {"id":"edge","label":"Edge","color":"#e8743b"} ],
  "nodes":  [ {"id":"user","label":"Usuário","icon":"user","group":"edge"},
              {"id":"cf","label":"Cloudflare","icon":"shield","group":"edge","note":"WAF + CDN"} ],
  "edges":  [ {"from":"user","to":"cf","label":"HTTPS","animated":true},
              {"from":"cf","to":"lb","animated":true} ]
}
```

- **node:** `id`, `label`, `icon` (nome do set), `shape` (formato; omita p/ `rounded`), `group` (opcional), `note`, `pos` ([x,y] fixa a posição).
- **edge:** `from`/`to`, `label` (opcional), `animated` (bool), `style` ("solid"/"dashed"), `fromSide`/`toSide` (`right`|`left`|`top`|`bottom` — omita p/ escolha automática pelo eixo dominante).
- **group:** `id`, `label`, `color`.

## Princípios

- **Um diagrama legível > um diagrama cheio.** Agrupe, dê nomes curtos, não jogue 30 nós soltos. Se o cenário é grande, sugira quebrar em diagramas (ex.: um por camada/fluxo).
- **O `flow.json` é a fonte da verdade** — versionável, editável; o HTML é gerado. Itere no JSON, não no HTML.
- **Ícone serve à compreensão**, não à decoração — escolha o que comunica o papel.
- **Identidade visual** das outras skills: light/dark, accent temático, live-reload.

## Limites

- **Fora do escopo neste ciclo:** subgrupos aninhados, waypoints manuais gravados no
  `flow.json` (a rota das setas é calculada), colaboração multiusuário e histórico entre
  sessões. Uma seta que precise desviar de um nó no meio do caminho ainda passa por trás dele:
  mova os nós ou quebre o diagrama.
- Focado em **fluxos, processos e arquiteturas pra apresentar/explicar**. O canvas é um editor de diagrama de verdade (arrastar da paleta, formas, multi-seleção, desfazer, apresentar), mas não é um programa de design gráfico livre: não há texto solto, imagem, desenho à mão nem camadas.
- O layout é determinístico em camadas/faixas (bom e previsível); grafos muito densos/cíclicos ficam legíveis mas não pixel-perfect — nesse caso, simplifique ou quebre em partes.
- Export SVG/PNG pela toolbar; PNG@2x/3x e PDF headless via `export_flow.py` (precisa de um
  Chrome/Chromium instalado — senão, cai no SVG/PNG da toolbar).
