# Changelog

Todas as mudanças relevantes deste marketplace são registradas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versões de cada skill seguem [SemVer](https://semver.org/lang/pt-BR/) no
`plugin.json` correspondente.

## [Não publicado]

### Adicionado
- `sw-flow-diagram` (v0.2.2): **quatro exemplos novos**, um de cada arranjo, em `examples/`:
  `aprovacao-de-despesa` (vertical, fluxograma clássico com decisão, espera, recusa e junção),
  `jornada-de-assinatura` (vertical, jornada em fases com caminhos de recuperação),
  `camadas-saas` (faixas por camada) e `microservicos-pedido` (grafo, com ida e volta entre os
  mesmos dois serviços). O `SKILL.md` ganhou a tabela dos exemplos e a regra de escolha do
  arranjo: processo com decisões pede vertical; caminho de request pede horizontal.

### Corrigido
- `sw-flow-diagram` (v0.2.2): no arranjo **em faixas**, dois nós da mesma faixa que caíssem na
  mesma coluna eram desenhados **exatamente um sobre o outro** e sumiam do diagrama (o `y`
  dependia só da faixa). Agora eles empilham dentro da faixa, e a faixa cresce para caber a
  maior pilha.

### Adicionado
- `sw-flow-diagram` (v0.2.0): **o editor aguenta diagrama grande.** O `flow.json` ganhou um
  contrato validado antes de qualquer gravação, o salvar virou atômico com detecção de
  conflito, e o editor passou a ter organização, navegação e edição em lote.
  - **Contrato e salvar seguro:** `scripts/flow_contract.py` recusa id repetido, ponta de
    aresta inexistente, grupo desconhecido, cor e enum inválidos, sempre dizendo o campo
    (`nodes[2].id`). O `POST /save` compara o hash do arquivo em disco: mudou por fora, responde
    **409** e o editor oferece recarregar ou baixar `flow-conflict.json`. O build roda antes da
    troca, e a troca do `flow.json` e do `flow.html` é atômica: falha no meio restaura os dois.
  - **Organizar, alinhar e distribuir**, com layout determinístico — o mesmo documento cai
    sempre no mesmo desenho.
  - **Navegar:** minimapa, estrutura, filtro por grupo e **foco de caminho**, que acende o menor
    caminho dirigido entre dois nós e nunca inventa caminho indo contra a seta.
  - **Edição em lote:** grupo, formato e ícone para todos os nós selecionados, e traço e
    animação para as conexões internas à seleção. O painel diz quantos itens pegou e um
    Ctrl+Z desfaz o lote inteiro.
  - **Conexões paralelas** entre os mesmos dois nós abrem em leque, cada uma com o seu rótulo,
    em vez de se esconderem uma atrás da outra; com grupo recolhido, a linha que representa
    várias mostra o número.
  - **Acessibilidade:** nome falado em cada botão, foco visível, todo nó alcançável por Tab
    (Enter seleciona), resultado de salvar e erro de validação anunciados em texto, e o botão
    passa a dizer "Salvar alterações" quando há pendência, em vez de só mudar de cor.
  - **Telas estreitas:** abaixo de 900px a paleta e o painel viram gavetas sobre o canvas;
    abaixo de 640px, abrir o painel recolhe a paleta.
  - **Paleta de componentes:** categorias recolhíveis (a primeira aberta), formas em duas
    colunas, e o catálogo passou de 73 para **148 componentes em 11 categorias** — entram
    IA / ML e Negócio / Processo, além de mais itens em todas as outras. Oito ícones novos
    (`brain`, `chat`, `money`, `truck`, `key`, `flask`, `chart`, `team`) para esses tipos não
    nascerem todos com o mesmo desenho.

### Corrigido
- `sw-flow-diagram` (v0.2.0): a paleta **não minimizava ao clicar**. O CSS dava `display:flex`
  à grade, e isso vence o atributo `hidden` — o estado alternava e nada sumia da tela. As
  miniaturas também mentiam: com raio de canto fixo em 13px numa caixa de 26px, "Processo"
  saía igual a "Início / Fim". Agora o detalhe em pixel encolhe junto com a caixa.
- `sw-flow-diagram`: os testes em Python exigiam `pytest`. Foram portados para a biblioteca
  padrão (`python3 -m unittest`), como o resto do marketplace — a skill roda na máquina de quem
  instala, sem dependência nova.

### Removido
- `sw-design-studio`: saiu do marketplace. O papel dela — decidir a direção visual — foi absorvido
  pela `sw-frontend-mockup-preview`, que decide **vendo** as variações em vez de entrevistar eixo
  por eixo. O glossário de técnicas do modo didático foi junto. `sw-brainstorming` e
  `sw-frontend-component-kit` deixaram de citá-la (`sw-brainstorming` v0.6.1).

### Adicionado
- `sw-frontend-mockup-preview` (v0.7.0): **decide a direção e barra o visual genérico de IA.**
  Adaptado, com texto próprio, do Impeccable (Apache-2.0) e da Taste Skill (MIT).
  - **Leitura do pedido** em uma linha antes de gerar — tipo de tela, público, linguagem e o
    modo (convencer, operar, ler, experimentar) — e uma pergunta só, e só quando a leitura
    diverge.
  - **Variações que diferem de verdade:** cada uma num eixo primário diferente (hierarquia,
    topologia, tipografia, cor, densidade, decomposição), presa à identidade da tela ou, sem
    design system, partindo de um referente do mundo do assunto. Um teste do "olhar
    semicerrado" antes de servir, incluindo "eu produziria isto para qualquer pedido?".
  - **Detector anti-slop** (`scripts/detectar.py`): varredura determinística, sem LLM e sem
    rede, de 17 padrões — texto em gradiente, preto puro em qualquer grafia, borda colorida
    lateral, sombra dura, halo colorido, easing elástico, emoji como ícone, dados "Jane Doe"
    (inclusive em `placeholder`), travessão no texto de interface, rótulo numerado, três colunas
    iguais (inclusive `grid-cols-3`), knob que não faz nada... Só olha o design, nunca a casca
    do harness; exceção declarada no HTML é listada com linha, nunca calada.
  - **Knobs ao vivo:** cada variação declara até 4 ajustes (faixa, segmentado, liga/desliga) e
    o harness desenha os controles — o usuário ajusta sem gerar de novo. `?v=2&k=acento:0.8`
    abre direto num estado, e `?limpo=1` esconde a casca para o screenshot.
  - **Vocabulário de refino** depois do primeiro render: mais ousado, mais calmo, enxugar,
    polir, tipografia, cor, layout, movimento, adaptar — cada uma gerando variações em facetas
    diferentes da própria dimensão.
  - **Registro da direção** no `DESIGN.md` do projeto quando ela é nova (paleta, tipografia,
    densidade, movimento, profundidade, assinatura, o que evitar) — é o que a component-kit lê.
  - Conferência do render também pelo Chrome da linha de comando, sem depender do Playwright;
    rodada única, com teto.
  - **A tela do preview foi refeita:** barra de uma linha, painel lateral com a variação em foco
    no topo e abas com contador (Ajustes, Direção, Notas, Detector), **comparar lado a lado**
    (cada coluna é um container próprio e o painel mostra a coluna clicada), **largura livre**
    arrastando a borda, largura total sem moldura, atalhos de teclado, e o estado inteiro na URL
    (o live-reload não devolve mais a tela ao início a cada edição).
  - **O usuário fala com o agente pela tela:** **Comentar** num elemento grava o pedido com o
    caminho do elemento, e **Seguir com esta** grava a variação escolhida com os knobs, a largura
    e as fontes testadas. O `serve.py` guarda isso em `.mockup/` (fora do live-reload, só aceita
    JSON da própria página e limita o tamanho), e o agente lê a cada turno.
  - **Fontes do Google Fonts, quaisquer:** dois campos, Título e Corpo, carregam qualquer família
    na hora; trocar o corpo não mexe nos títulos. A aba Direção mostra a paleta e as fontes lidas
    do que está renderizado, e o selo do detector aponta no canvas o elemento de cada achado.
- `sw-frontend-component-kit` (v0.3.0): **a demo que ensina.** Cada tela de componente da página
  de demo passa a ter a barra de controles no conteúdo, um palco de estúdio com a peça viva,
  **todos os tipos** de uma vez (variantes × tamanhos e estados, e as formas extras), quando usar
  e quando não usar cada variante, e de 3 a 5 **exemplos em contexto** com o porquê, sem nenhum
  bloco de código. A referência visual aprovada vem junto (`assets/demo-estudio.html`) e o
  catálogo do que mostrar, componente por componente, está em `references/demo-que-ensina.md`.
  - A direção do kit é escolhida numa **amostra** (Button, Input, Card, Badges e uma linha de
    tabela) com variações em eixos diferentes, e não mais só no botão.
  - Bootstrap **sem visual genérico**: pergunta a cena de uso e o tom em vez de oferecer
    paletas prontas, fontes do Google Fonts escolhidas pelo tom, neutros tingidos, e o piso
    anti-genérico aplicado a cada componente.

### Corrigido
- `sw-frontend-mockup-preview` (v0.7.0): o que a revisão mostrou usando a skill como está
  escrita. O mais sério: **um projeto sem design system saía com os tokens de exemplo do
  harness** (slate, azul-500, Inter — o visual "padrão de IA" mais reconhecível), e o detector
  dava limpo. Agora esses tokens são marcados como exemplo, e sem design system cada variação
  traz a própria paleta. Também: variação montada em `<div>` não era analisada; declarar exceção
  com justificativa derrubava o detector; toggle com padrão `"false"` abria ligado; valor fora
  do mínimo e do máximo gravava na variável enquanto o slider mostrava outro número.
- `sw-frontend-component-kit` (v0.3.0): dizia "não invoque outras skills" e, na mesma fase,
  mandava oferecer a mockup. Agora diz o que faz: só **oferece** a mockup, pelo menu.

### Adicionado
- `sw-infra-audit` (v0.9.0): **as filas do broker respondem**. O papel `fila` deixa de ser mudo:
  o adaptador `admin_http` lê a API de administração e responde **filas** (mensagens prontas,
  não confirmadas e consumidores), **consumidores por fila** e **entrada × saída**. Fila com
  mensagem pronta e nenhum consumidor vira o achado `fila_sem_consumidor` (alto), um por fila,
  identificado como `nome@vhost`. É a primeira regra da skill que nasce de uma **medida**, e
  não de como o serviço está declarado — o campo `limiar` existia no registro de perguntas
  desde a v0.7 e nenhuma linha do código o lia.
  - O adaptador não sabe o que é o produto: a família é descrita em
    `references/apis/amqp-mgmt.toml` (o nome é do formato, não do produto) numa **linguagem
    fechada** — ponteiro JSON, campos, transformações e contas declaradas. Sem expressão
    arbitrária: o limiar tem parser próprio, nunca `eval`.
  - **A primeira porta autenticada da skill.** A senha vem do ambiente pelo nome declarado em
    `senha_env`, vai só em header, é amarrada a (alvo, host, porta) e não aparece no
    `alvos.toml`, no argv, no `report.json`, no HTML nem no PDF — um teste de ponta a ponta
    procura a senha em todo arquivo gerado. Senha escrita na própria URL é recusada ao ler a
    configuração.
  - **Só leitura, verificável:** `GET` fixado no código, catálogo que recusa rota de escrita e
    caminho que saia do host, e o único parâmetro de URL aceito é `columns`.
  - O relatório desenha lista de vários campos como **tabela** e mostra as 10 primeiras, dizendo
    quantas ficaram de fora; a lista inteira fica no `report.json`. O corte é de exibição: o
    limiar vê **todas** as filas. A lista de filas é ordenada pelo total **acumulado**
    (prontas + não confirmadas), então a fila travada — consumidor conectado que recebe e nunca
    confirma, o caso que a regra não vê — aparece no topo.
  - O carregador do catálogo recusa rota de escrita, rota GET que devolve segredo
    (`/api/definitions`, `/api/users`, `/api/parameters`, `/api/connections`...) e qualquer
    parâmetro de URL que não seja `columns`.
  - A SKILL.md orienta criar um usuário só para a auditoria, com a tag `monitoring` e **sem**
    permissão de configure ou write.
  - `configurar.py aceitar` ganhou `--componente`, e a SKILL.md orienta o aceite mais estreito
    possível (`--objeto emails@staging`).

### Corrigido
- `sw-infra-audit` (v0.9.0): o que a revisão por lote achou em seis rodadas, sempre reproduzido
  em teste antes da correção:
  - **senha no PDF**: `admin_url = "http://usuario:SENHA@host"` passava na validação e ia crua
    para o componente, o `report.json`, o HTML e o PDF. A guarda contra credencial na URL foi
    para `check_allowed`, por onde toda chamada de rede passa.
  - **300 filas órfãs davam zero achados**: com o corte no top 10 feito na extração, o limiar
    só via as filas mais cheias. O corte passou a ser do relatório.
  - **broker com estatísticas desligadas dava verde**: 300 filas sem contador, zero achados. Lista
    em que nenhum item traz os campos que a regra compara agora é `sem dados`, com esse motivo.
  - **alvo verde com achado crítico aberto**: a saúde era decidida antes das perguntas. E, ao
    corrigir isso, um achado aceito continuava deixando o alvo vermelho — a saúde passou a ser
    recalculada depois dos aceites, e só por achado nascido de limiar (a nota do coletor docker
    já conta os achados dele).
  - **ranking errado em silêncio**: um nome de campo errado em `transformar` deixava o número
    como texto, e "9" vinha antes de "42".
  - **um NaN abortava a gravação do relatório inteiro**; resposta acima de 4 MB era cortada e
    dita como "a API não respondeu"; o cache morria a cada pergunta (três downloads inteiros do
    broker); o timeout de comando era usado em HTTP; 403 e redirect viravam "não reconheci a
    família"; um adaptador com bug impedia o próximo de responder.
  - **senha no terminal**: colar `amqp://usuario:SENHA@host` na `admin_url` fazia a mensagem de
    recusa repetir a URL inteira. A credencial é checada antes do esquema, e nenhuma mensagem
    repete a URL.
  - três frases da própria documentação eram falsas no código (a fila travada "visível", o corte
    "dito em toda lista", o carregador "recusando rota de escrita"); a revisão as conferiu uma a
    uma, e o código passou a fazer o que o texto diz.
  - a remediação ensinava a pôr a senha no argv (`curl -u "$USUARIO:$SENHA"`); agora o `curl`
    pergunta, e uma trava varre todos os arquivos de remediação atrás do padrão.
  - o nó da topologia despejava a lista de filas inteira como texto cru — três páginas A4; e o
    canto arredondado das tabelas cortava a primeira letra da primeira coluna.

### Adicionado
- `sw-infra-audit` (v0.8.0): **o relatório aguenta volume**. Uma auditoria real trouxe 213
  achados e o PDF saiu com **121 páginas A4** — 75 deles eram a mesma regra, com um único
  detalhe distinto entre os 75, e cada ocorrência levava um cartão inteiro com o bloco de
  remediação repetido. Agora achado da mesma regra vira **um bloco com a remediação uma vez** e
  as ocorrências em **linha densa, três colunas na impressão**: 121 → 23 páginas, com todas as
  213 ocorrências ainda no relatório. Agrupar não é esconder — o que saiu foi a repetição.
  - A chave do agrupamento é `(regra, severidade)`, não a regra sozinha: um aceite rebaixa a
    severidade de UMA ocorrência, e fundir as duas faria o relatório anunciar gravidade que
    aquela ocorrência não tem.
  - Seção nova **"O que falta declarar"**, e o script `pendencias.py` que a alimenta: quando um
    componente não responde, o relatório passa a dizer **por quê** e o que escrever no
    `alvos.toml` para resolver. Sem isso, 57 componentes apareciam com nome, papel e silêncio, e
    quem lia concluía que a skill não funcionava.
  - A seção **Insights** deixa de imprimir um cartão por componente mudo: eram 57 repetições da
    frase "nenhuma pergunta para este papel nesta versão", seis páginas A4. Os que ficam de fora
    são contados, com link para a seção que explica cada um.
  - Passo **3b** no fluxo: antes de interpretar, checar o que ficou calado e **perguntar** se o
    `metricas_url` entra agora. Coletar com exit 0 não quer dizer que alguém respondeu alguma
    coisa.

### Corrigido
- `sw-infra-audit` (v0.8.0): a remediação é escrita em markdown e era impressa **achatada num
  parágrafo só**, com as crases e o "1." no meio do texto corrido. O template sempre teve CSS
  para `.fix ol` e `.fix pre` — o desenho contava com lista numerada e bloco de código, e o
  renderizador nunca gerava nenhum dos dois. Agora `_rich` entende parágrafo, lista (inclusive
  item que continua na linha seguinte, que é como os arquivos de 95 colunas quebram), bloco de
  código, negrito e código inline. Tudo continua escapado antes: o conteúdo vem de arquivo e
  nada nele abre tag.
- `sw-infra-audit` (v0.8.0): quando o PDF falhava, a mensagem era **"PDF não gerado (sem
  Chromium)" para qualquer causa** — numa máquina com Chromium instalado e uma conversão que
  estourou o tempo, ela mandava o operador procurar um navegador que já estava lá. Agora o
  motivo é o verdadeiro, e o limite de tempo subiu de 60s para 180s.
- `sw-infra-audit` (v0.8.0): o sumário lista as seções a partir de um registro separado do
  template — dois lugares para a mesma verdade. Seção acrescentada no HTML e esquecida no
  registro simplesmente não aparecia no sumário; removida do HTML e esquecida no registro
  deixava âncora morta no PDF. Nenhum dos dois quebrava teste. Agora quebra.
- `sw-infra-audit` (v0.8.0): a capa empurrava o sumário inteiro para a folha seguinte (ele era
  indivisível) e abria o relatório com meia página em branco.

### Adicionado
- `sw-infra-audit` (v0.7.1): **toda decisão da skill passa a ser menu clicável**
  (`AskUserQuestion`), com a tabela dos momentos em que perguntar: confirmar os alvos da rodada,
  criar o primeiro `alvos.toml`, acertar o `.gitignore`, propor `metricas_url`, registrar risco
  aceito, decidir o que fazer com aceite vencido e gerar o PDF no fim. Numa auditoria isso não é
  preferência de interface: quem responde está decidindo em que máquina de produção se vai
  tocar, e opção clicável com o alvo escrito por extenso erra menos que texto livre. Junto vem a
  contrapartida: **não perguntar o que a skill descobre sozinha** — pergunta serve para decisão
  e autorização, não para suprir leitura que o agente não fez.

- `sw-infra-audit` (v0.7.0): **relatório redesenhado**, com três seções novas e duas decisões de
  honestidade embutidas no desenho.
  - **Topologia**: os componentes aparecem em camadas — quem recebe o tráfego, quem processa,
    quem guarda —, cada um com quantos achados tem em aberto. A legenda diz, com todas as
    letras, que o agrupamento é por **papel** e **não é dependência medida**: a skill observa o
    papel de cada componente, não quem chama quem, e desenhar seta de dependência a partir
    disso seria afirmar o que ela não viu.
  - **Instrumentos**: mostrador com faixa de tolerância — mas **só para pergunta que declara a
    faixa**. Hoje isso é a latência p95 (bom até 700 ms, ruim a partir de 1.500). Volume de
    requisições não vira mostrador porque "bom" depende do serviço; agulha sem tolerância
    declarada sugere uma leitura que ninguém definiu, e um teste impede que apareça.
  - **Sumário que conta**: cada linha traz o que tem dentro e a contagem real (3 componentes,
    1 achado aberto, 2 saíram desde a rodada anterior). Continua sem número de página — e
    continua clicável no PDF, porque o Chromium converte as âncoras em link com destino de
    página.
  - Capa com o estado de cada alvo em palavra, achados com trilho de gravidade, e cor usada só
    onde significa alguma coisa.

- `sw-infra-audit` (v0.6.0): **insights por sistema e como resolver cada achado** — o plano 1 do
  dossiê `2026-09-19-insights-por-sistema-e-remediacao` está completo.
  - Cada componente do alvo recebe um **papel** e responde as **perguntas** daquele papel; quem
    responde é um **adaptador**, e toda resposta carimba a **fonte**. O que não foi respondido
    aparece com o motivo — nunca como zero.
  - **Catálogo de remediação**: um arquivo por regra (20 regras), com por que importa, como
    resolver com comando, **como confirmar que resolveu** e quando NÃO fazer. É versionado e
    revisado em pull request, em vez de gerado a cada rodada. Os comandos são para exibir;
    a auditoria nunca executa nada.
  - **Relatório novo**, com sumário no topo, seção de insights por componente e o bloco de
    remediação em cada achado. O `impact.py` (cenário → consequência) volta a aparecer depois
    de duas versões sendo calculado e descartado.
  - Sumário **sem número de página**: o Chromium não tem `target-counter`, e descobrir as
    páginas numa segunda passada dependeria de ferramenta externa — duas máquinas gerariam
    relatórios diferentes para a mesma entrada.

### Alterado
- `sw-infra-audit` (v0.4.0): **o alvo passa a ter componentes** — o esqueleto para interrogar
  cada peça da infraestrutura pelo papel dela. É a primeira metade do plano 1 do dossiê
  `2026-09-19-insights-por-sistema-e-remediacao`.
  - `report.json` **v3**: cada alvo carrega `componentes[]`, e cada componente guarda as
    respostas das perguntas do seu papel. O `build_report` recusa o v2 com mensagem — sem
    migração silenciosa; relatório antigo fica onde está.
  - **Registro explícito de regras** (`lib/regras.py`): as 22 regras que viram achado, cada uma
    com severidade, origem e a marca "esperada". Um teste cruza o registro com o que os
    produtores realmente emitem — divergência de severidade agora falha a suíte em vez de sair
    no relatório com a gravidade errada. Saiu também uma entrada morta de `rule_meta`.
  - **Papel do componente** (`lib/papel.py`) derivado do `kind` que já existia, com teste de
    consistência: `kind` novo sem papel falha a suíte em vez de virar `app` calado.
  - **Achado com endereço**: nasce no componente e sobe para o alvo carregando de onde veio.
    O aceite ganhou mira — duas filas com o mesmo problema, aceitar o risco de uma não silencia
    a outra. `[[aceite]]` e `[insights]` ganharam allowlist de chave: um `compomente` digitado
    errado viraria aceite do alvo inteiro, mais amplo do que o dono pediu.
  - **Histórico não some mais**: rodada anterior em v2 ainda gera diff, comparando sem o
    componente dos dois lados (senão o mesmo achado sairia como resolvido E como novo) e
    dizendo a ressalva no relatório.
  - `alvos.toml` aceita `[[alvo.componente]]` (nome, papel, admin_url, metricas_url,
    senha_env — o valor da senha nunca no arquivo) e o `config.toml`, `[insights]` e
    `relatorio.ip_completo`.

- `sw-infra-audit` (v0.3.0): **a configuração do projeto também vai para `docs/infra/`** — o que
  era `.sw-infra-audit.toml` na raiz agora é `docs/infra/config.toml`, e a skill passa a ter um
  lugar só: alvos, configuração e relatórios na mesma pasta. O arquivo antigo na raiz continua
  sendo lido enquanto o novo não existir.
  Ele segue **versionado** de propósito (escolha de alvos e riscos aceitos passam por revisão em
  PR), o que muda a forma do `.gitignore`: `docs/infra/*` mais `!docs/infra/config.toml`. A linha
  antiga (`docs/infra/`) ignora o diretório inteiro — nenhuma negação resgata um arquivo lá
  dentro —, então `configurar.py ignorar` a **substitui** quando a encontra.
- `sw-infra-audit` (v0.2.0): **o arquivo de alvos passa a morar no projeto**, em
  `docs/infra/alvos.toml` — a mesma pasta do relatório, que já fica fora do git. O
  `~/.config/sw-infra-audit/alvos.toml` deixa de ser lido; `configurar.py migrar` traz o conteúdo
  do antigo quando ele existe. Os alvos seguem `relatorio.pasta`: mudou a pasta, mudaram os dois
  (duas pastas seriam duas verdades).
  Como o arquivo guarda conexão e agora vive dentro da árvore do repositório, a skill **confere
  com `git check-ignore`** antes de ler ou escrever e **recusa** se a pasta não estiver ignorada —
  arquivo de conexão versionado é conexão publicada. O `migrar` acrescenta a linha ao `.gitignore`
  antes de criar o arquivo. Novo `lib/ignorado.py`, o único ponto que roda `git` (a restrição de
  "um único ponto de subprocesso" passou a listar os três pontos, cada um com seu binário).

### Corrigido
- `sw-infra-audit` (v0.3.1): duas travas que pareciam existir e não existiam — as duas com
  prova por mutação.
  - **Egress passa a exigir host E porta.** Confirmar um host autorizava qualquer porta dele;
    como a coleta vai passar a perguntar a componentes em portas de administração, isso viraria
    varredura de portas na máquina que o dono confirmou. Porta impossível no `alvos.toml`
    (erro de digitação) agora falha na leitura do arquivo, com mensagem de configuração, em vez
    de morrer dentro do coletor como "erro interno".
  - **O ambiente do processo filho virou base positiva.** Antes copiava o seu ambiente inteiro
    menos quatro variáveis — e lista de proibidos só protege do que alguém lembrou de escrever
    nela. Como a credencial de um alvo chega justamente pelo ambiente, a senha do banco viajaria
    dentro de todo comando docker. Agora o filho recebe só o mínimo (`PATH`, `HOME`, `LANG`,
    `LC_ALL`, `TZ`), os caminhos de que o cliente docker precisa (`SSH_AUTH_SOCK`,
    `DOCKER_CONFIG`, `XDG_RUNTIME_DIR`) e o que o chamador declarar.

- `sw-infra-audit` (v0.1.1): quatro achados do code review, todos com teste de regressão.
  - `DOCKER_HOST` herdado do shell anulava o `DOCKER_CONTEXT` do alvo (ele tem precedência no
    docker): a coleta falaria com outra máquina e o relatório assinaria com o nome do alvo
    confirmado. O ambiente do processo filho agora sai sem `DOCKER_HOST`, `DOCKER_CONTEXT`,
    `DOCKER_TLS_VERIFY` e `DOCKER_CERT_PATH`, e recebe só o context do alvo.
  - `configurar.py alvos --sugerir` estourava `TypeError` em toda execução (chamava
    `assemble_report` com um parâmetro inexistente) — e, depois disso, lia o daemon **local**
    em vez do context pedido. Agora todo comando da proposta leva o context, e o host vem do
    endpoint do próprio context.
  - `configurar.py aceitar` gravava data impossível quando o mês de destino é mais curto
    (31/03 + 6 meses virava "2026-09-31"), e a auditoria seguinte morria com traceback ao ler
    o aceite. A data gruda no último dia do mês, `--desde` inválido é recusado antes de escrever,
    e o `collect.py` para com mensagem — nunca com traceback — diante de aceite mal escrito.

### Removido
- `sw-cluster-audit` (era v0.10.1): substituída pela `sw-infra-audit`. O `report.json` v1 não é
  lido nem comparado pelo v2 — auditorias antigas ficam onde estão, como histórico.

### Alterado
- `sw-plan` (v0.5.0): ao concluir tasks que mexeram em teste, oferece o diagnóstico da
  `sw-auto-test`.
- `sw-code-review` (v0.1.2): passa a indicar a `sw-auto-test` para qualidade de teste.
- `sw-plan` (v0.4.0): ao concluir todas as tasks, oferece gerar a descrição do PR com a
  `sw-pr-message` quando a branch tem commits fora da base.
- `sw-code-review` (v0.1.1): passa a indicar a `sw-pr-message` para gerar a mensagem do PR.
- `sw-brainstorming` (v0.6.0) e `sw-plan` (v0.3.0): **spec, plano, briefing e referências passam
  a viver num dossiê único por trabalho** — `docs/specs/<data>-<slug>/` com `spec.md`, `plan.md`,
  `briefing.*` e `referencias/`. Antes o mesmo trabalho ficava partido entre `docs/specs/` e
  `docs/plans/`, com nomes diferentes e nada ligando os dois. `referencias/` é onde entra o
  material de apoio (print, PDF do cliente, export de diagrama) que o spec cita em vez de
  descrever de memória.
  Novo `scripts/dossie.py` (`novo`/`listar`/`estado`/`indice`): cria o dossiê, controla o estado
  (rascunho → aprovado → em-execucao → concluido) e regenera o índice em `docs/specs/README.md`.
  É script e não instrução porque um índice mantido à mão passa a mentir no primeiro esquecimento.
  A brainstorming agora **oferece continuar um dossiê existente** antes de abrir outro, e o
  auto-review passa a **apontar** fitness functions frouxas, referência citada mas ausente, e
  quando o design ganharia um diagrama — sugerindo, sem gerar por conta própria.
  O dossiê do `sw-cluster-audit` foi migrado com `git mv` (histórico preservado).

### Adicionado
- `sw-infra-audit` (v0.1.0): **a auditoria deixa de ser de um cluster e passa a ser por ALVOS**.
  Substitui a `sw-cluster-audit`, que sai do marketplace. Na v1 os alvos são cluster Docker e
  endpoint HTTP (saúde + validade do certificado); banco de dados é o próximo ciclo. O relatório
  (`report.json` v2) abre pelo **inventário** — o que existe, onde vive e em que estado —, tem nota
  por alvo e **nenhuma nota agregada**, porque número único de saúde vira meta e meta vira teatro.
  Configuração em três camadas: padrões da skill < `~/.config/sw-infra-audit/alvos.toml` (fora de
  qualquer repositório) < `.sw-infra-audit.toml` do projeto (versionado). **O arquivo versionado não
  define conexão**: host, porta, usuário e credencial só existem na máquina do dono — um arquivo
  vindo de pull request não redireciona conexão nem credencial. Toda execução exige confirmação
  explícita dos alvos, e alvo não confirmado não é tocado (mas aparece como `sem dados`, para o
  inventário não mentir por omissão). Risco já decidido vira **aceite** com justificativa e data de
  revisão: sai da nota, ganha seção própria, e volta a contar quando vence. Falha de acesso é
  `nao_coletado` com motivo, nunca achado. Quatro restrições com teste e provadas por mutação:
  auditar não escreve fora da pasta da execução, nada executa sem confirmação, nenhum segredo chega
  ao relatório, e mesmas entradas geram o mesmo relatório byte a byte.
- `sw-auto-test` (v0.1.0): **publicada, com um modo novo de diagnóstico da suíte de testes**.
  Além de gerar testes, ela agora avalia os que já existem: apura os fatos com a ferramenta nativa
  da stack (pytest, vitest/jest, phpunit), o agente julga só os arquivos suspeitos, e sai um
  `test-health-report.md` com notas por dimensão (confiabilidade, isolamento, cobertura,
  legibilidade, velocidade) e achados por confiança, seguido de correção guiada em lotes. Dimensão
  sem dado fica `⚪ sem dados` em vez de estimativa, e não existe nota agregada — número único vira
  meta, e meta de cobertura não mede teste bom. A execução da suíte é opt-in: descoberta primeiro,
  comando à vista antes de confirmar, e parada quando há banco no ambiente de teste (inclusive
  declarado no `phpunit.xml`). No modo gerar entraram baseline, **prova do vermelho** (quebra o
  código de propósito para confirmar que o teste acusa, com backup e varredura de resíduo abrindo
  toda execução), determinismo por padrão e a proibição de forçar verde. O `SKILL.md` caiu de 411
  para 219 linhas, com o resto em `references/`, e ganhou gatilhos em português. Quatro restrições
  com teste: escrita confinada, nada executa sem aprovação, restauração garantida por hash e
  relatório determinístico — as três primeiras provadas por mutação.
- `sw-pr-message` (v0.1.0): **gera o `PR-MESSAGE.md` de uma branch com as mudanças agrupadas por
  tipo** — Novas funcionalidades, Ajustes, Correções, Removido, Segurança, Interno, Como testar e,
  em hotfix, causa/impacto/rollback. Substitui a `sw-git-pr-generator`, que listava um item por
  commit, lia só o assunto e escolhia a base em ordem fixa `main → master → develop` (num caso
  medido, descreveria 205 commits em vez de 9). A base agora é o candidato com menos commits à
  frente, parando quando a branch já está contida num deles; os commits vêm sem merges e o diff a
  partir do merge-base. Script coleta e valida, agente interpreta: o render recusa commit esquecido
  e garante ordem, títulos, idioma e ausência de emoji. Os scripts só executam git de leitura (lista
  fechada, recusa por prefixo, `--end-of-options`), não acessam a rede e só escrevem no `git-path`,
  no `info/exclude` e no `PR-MESSAGE.md`, e o render é determinístico — as quatro restrições têm teste.
- `sw-flow-diagram` (v0.1.0): **publicada no marketplace**, com o editor de canvas reescrito.
  O `flow_editor.js` (281 linhas, 40 delas acima de 160 caracteres, variáveis de 1-2 letras)
  virou `scripts/editor/*.js` em módulos por responsabilidade, concatenados e **embutidos** no
  `flow.html` pelo build — o HTML gerado passou a ser um arquivo único, que abre até direto do
  disco (módulos ES não carregariam via `file://`).
  Novidades: **desfazer/refazer** por snapshot, **multi-seleção** (Shift, laço, Ctrl+A) com
  arrasto em grupo, **painel de propriedades**, **guias de alinhamento** magnéticas,
  **paleta lateral que se arrasta** pro diagrama, **21 formas de fluxograma** (decisão, banco,
  documento, subprocesso…), **4 portas de conexão por nó** (cima/baixo/lados, com o lado
  gravado na aresta), **busca de nó** (Ctrl+F), **grupos recolhíveis** que religam as arestas
  à caixa, e **modo apresentação** passo-a-passo em ordem topológica (`?present=N` abre direto).
  Corrigido o packet que piscava no canto: `animateMotion` soma translação sobre `cx`/`cy`, então
  o círculo fica em (0,0) e nasce invisível até a sua vez.

### Alterado
- **Segurança:** o gate (`scripts/scan_secrets.py`) passou a detectar **IP público** em conteúdo
  publicável, e `sw-cluster-audit` (v0.10.1) teve o IP real do cluster de produção — que havia
  ficado numa docstring e em fixtures de teste — trocado pelas faixas reservadas para
  documentação (RFC 5737). Num repositório público, o IP do host onde a API do Docker escuta na
  2376 é superfície de ataque, mesmo com mTLS. A regra ignora faixas privadas, loopback,
  link-local e as próprias faixas de documentação, então não gera ruído.
- `sw-cluster-audit` (v0.10.0): **nós do cluster viram tabela comparativa** (direção de design
  definida com a `sw-design-studio`). Em cards, cada rótulo se repetia uma vez por nó e metade
  dos valores era idêntica (`Ready`, `Active`, `linux/x86_64`) — a repetição consumia a largura
  que faltava aos valores, e "4 vCPU · 7.8 GB" quebrava no meio. Agora o rótulo aparece 1×, a
  leitura é horizontal (que é como se compara nó com nó) e **células que divergem da maioria são
  marcadas** em tom neutro — divergir não é sinônimo de risco, o manager ter mais CPU é normal.
  As falhas saíram de dentro das células e viraram lista agrupada **por código de saída**, com a
  pista do que cada código significa: revela que o mesmo `exit 137` em serviços não relacionados
  de vários nós é UM evento (um restart), não N problemas. A tabela quebra entre páginas com o
  cabeçalho repetido (`table-header-group`), senão a metade seguinte vira coluna de números sem
  dono. Removidos `_node_cards` e o CSS `.node`, agora órfãos.
- `sw-cluster-audit` (v0.9.0): **layout do PDF — mesmo conteúdo em 14 páginas em vez de 19**,
  com mais respiro. Margem do papel de 10mm→7mm nas laterais (+6mm de largura útil), padding e
  entrelinha maiores nos cards, e cards de nó em 4 colunas no papel (2 colunas deixavam a linha
  do grid alta demais e desperdiçavam página). O ganho maior veio da paginação: blocos de texto
  longo (impacto, recomendação, achados, stack) deixaram de ser indivisíveis — marcá-los assim
  empurrava o bloco inteiro e abandonava até 40% de papel em branco; agora fluem entre páginas e
  o que continua atômico é a unidade de leitura (um passo, um bloco de comando, uma linha de
  tabela). O plano perdeu o fundo preenchido: retângulo colorido cortado por quebra de página
  deixava faixa vazia no rodapé — virou régua lateral. Rodapé vazio médio: 9%, pior caso 16%.
  Corrigido também o rótulo colidindo com o número nos cards de dimensão.
- `sw-cluster-audit` (v0.8.0): **pontos de impacto passam a trazer plano de execução, não dica.**
  Cada ponto ganha uma lista ordenada de passos com comando pronto e o porquê da ordem, derivada
  dos fatos coletados: nº de managers reais (`docker node promote` já com os hostnames), storage
  do ACME do ingress (volume local vira passo bloqueante ANTES de escalar, senão o TLS quebra),
  e serviço com estado ganha passo próprio — nunca "suba 2 réplicas" para um banco, que daria
  duas instâncias brigando pelo mesmo volume. `mounts` passou a ser gravado por serviço para
  viabilizar a detecção do ACME.
- `scripts/sync_skill.py`: **o aviso de dado pessoal passou a respeitar os excludes do rsync.**
  Ele varria a origem inteira, incluindo `__pycache__`/`.ruff_cache`, e cuspia dezenas de avisos
  por sync sobre arquivos que nunca são publicados — gate que grita à toa é gate que se aprende
  a ignorar. Agora só olha o que de fato vai pro repo, e pula binário em vez de lê-lo com
  `errors="ignore"`. `.ruff_cache`/`.mypy_cache` entraram na lista de exclusão.
- `sw-cluster-audit` (v0.7.3): **saúde para de acusar migration como serviço caído.**
  `is_job_service` passa a aceitar task `Complete` em serviço cujo `kind` **não roda
  continuamente** — banco, fila, cache, busca e ingress ficam fora da exceção, então um postgres
  fora do ar continua sendo reportado. Certificado de cliente com validade > 3 anos virou
  **ponto de impacto** (credencial root-equivalente, sem revogação em `--tlsverify`; `ssh://`
  como saída para CI/CD), e a recomendação de **fechar a porta 2376 no firewall deixou de ser
  padrão** — quebra CI/CD hospedado e o mTLS já é a barreira. `completed_job` passou a exigir
  **nenhuma task ativa**: só `any(Complete)` isentava também worker que roda e reinicia saindo
  com 0, que ficaria mudo no dia em que caísse de verdade.
- `sw-brainstorming` (v0.5.0): **spec mais forte — anti-over-engineering + pronta pra execução**
  (baseado em pesquisa web 2025–26: Spec Kit/Kiro, *Building Evolutionary Architectures* 2ª ed.,
  Shape Up, context engineering da Anthropic). O spec passa a fechar com **Não-objetivos**,
  **Restrição de simplicidade** ("a menor solução que resolve"), **Appetite** e **MVP vs MLP**;
  ganha seção **Decisões (estilo ADR)** (contexto · decisão · alternativas descartadas ·
  consequências) e **2-4 fitness functions verificáveis** em specs substanciais (ex.: "p95 <
  200ms", "domínio sem import de infra"). Novo princípio "spec = contexto pro agente (altitude
  certa), não prosa" + item no auto-review cobrando não-objetivos/simplicidade/fitness-functions.
  Tudo proporcional ao tamanho (feature pequena leva versão enxuta).
- **Trio de design — quick wins + consolidação de tokens** (`sw-design-studio`,
  `sw-frontend-component-kit`, `sw-frontend-mockup-preview`):
  - **Tokens (fonte única):** `token-extraction.md` da mockup-preview vira o guia **canônico**
    (corrigido: usava seletores mortos `.panel--light/dark` → agora `[data-theme]`); studio e
    component-kit apontam pra ele em vez de duplicar a lógica.
  - **component-kit:** removida a contradição "autossuficiente, não invoque outras skills" (é um
    trio); nota **Stack-agnostic** (idioma por stack: Vue/React/Svelte/Angular/vanilla); consome a
    **Direção da design-studio/`DESIGN.md`** e pula a exploração via Button; corrigida a promessa
    do preview (a mockup-preview não ingere componentes reais → ver o kit é pela demo do projeto);
    `evals.json` com `skill_name` corrigido (pré-`sw-`) + **fixtures criadas** (eram inexistentes).
  - **design-studio:** Step 2 deixa de abrir menu de referência em **Autopilot** (contradição) e a
    referência entra junto de "tom & ousadia"; fallback de preview reaproveita o harness da irmã.
  - **mockup-preview:** ganha **consciência do arsenal** (oferece design-studio antes / component-kit
    depois); `serve.py` agora escuta em **`127.0.0.1`** por padrão (0.0.0.0 vira opt-in); notas sobre
    `?font` fora do mapa, `overflow` do frame no 5b e animação de entrada × troca de aba.
- `sw-brainstorming` (v0.4.0): **modo exploração ("Explorar a fundo")** — no passo 2, um loop
  divergente **opcional** de ideação por **lentes** (JTBD, divergir, desafiar suposições, flip de
  restrições, referências, riscos & bordas); a skill escolhe 2-3 conforme a ideia, pergunta uma a
  uma (com "Pular"/"Other") e oferece **convergir** a cada ~2 lentes (sem loop infinito). A síntese
  **"Exploração & decisões"** alimenta as abordagens, vira seção do spec e entra no Briefing.
  Catálogo em `references/exploration-lenses.md`. "Direto" continua o padrão (retrocompatível).
- **Rename:** `sw-writing-plans` → **`sw-plan`** (pipeline mais claro: brainstorming → plan → build).
  ⚠️ muda o comando de install (`/plugin install sw-plan@ai-marketplace`). Também: o plano salva
  em `docs/plans/` do projeto (versionável, fallback `~/.claude`); **revisor-juiz de execução
  escalonável** (Sem / por task-batch / no fim), consultivo, integrado nos dois modos; e nota
  **Stack-agnostic** (detecta linguagem/runner de teste reais; Python/pytest é só ilustração).
- `sw-brainstorming` (v0.3.0): o "resumo não-técnico" vira **"Briefing"**; o spec passa a salvar
  em **`docs/specs/`** do projeto (default, versionável) com fallback; nova seção **"Feature
  visual? Sugira as skills de design"** (arsenal: a skill analisa se é UI e sugere
  `sw-design-studio`/`sw-frontend-mockup-preview` via menu). Refs à `sw-plan` atualizadas.
- `sw-frontend-component-kit` (v0.2.0): na Fase 5, além da página de demo, **oferece via
  `AskUserQuestion` ver os componentes** — rodar a demo (`/dev/components`) ou um **preview
  isolado** via `sw-frontend-mockup-preview` (visualizar é o padrão).
- `sw-brainstorming` (v0.2.0): **revisor opcional escalonável** — no início do fluxo completo
  pergunta uma vez o nível de revisão (Sem revisor / Só no spec / Design + spec / Em cada
  checkpoint); um subagent revisor **consultivo** (não edita, não aprova) entra no design e/ou
  no spec conforme o nível. Novo template "design/checkpoint" no reviewer-prompt.
- `sw-frontend-mockup-preview` (v0.2.0): harness redesenhado — **variações em abas no topo**
  (uma tela por vez, sem empilhar) e **preview responsivo** (toggle 📱/💻/🖥/⛶) com
  responsividade real via `@container`; tema vira toggle ao vivo (canvas único). SKILL.md
  atualizado e verificado por screenshot (Playwright).
- `sw-frontend-mockup-preview` (v0.3.0): passo opcional de **auto-conferência do render**
  (passo 5b) — quando o Playwright está disponível, a skill oferece via `AskUserQuestion`
  tirar screenshot do mockup e conferir/consertar o óbvio antes de entregar a URL.
- `sw-frontend-mockup-preview` (v0.6.0): **seletor de fonte** no harness — dropdown na barra
  pra trocar a tipografia do mockup ao vivo (carrega o Google Font sob demanda; "Projeto" volta
  à fonte dos tokens) + URL param `?font=<nome>` pra screenshots. `autocomplete="off"` evita a
  restauração de formulário do Chrome sobrescrever o estado.
- `sw-frontend-mockup-preview` (v0.5.0): pergunta de **tema com 3 opções** (Claro/Escuro/Ambos)
  e orientação para usar **imagens de placeholder público** (Lorem Picsum, pravatar, placehold.co)
  quando o componente mostra foto — hotlink ou baixar pro dir do mockup.
- `sw-frontend-mockup-preview` (v0.4.1): a auto-conferência roda **sem interrupção**
  (ferramentas de leitura do Playwright pré-autorizadas, sem prompt a cada ação) e
  **fecha o browser** (`browser_close`) ao terminar.
- `sw-frontend-mockup-preview` (v0.4.0): auto-conferência mais **rápida** — harness aceita
  estado por URL (`?vw`/`?theme`/`?v`), então o 5b captura sem cliques (1 navigate + 1 shot),
  reusa o browser, usa `domcontentloaded` e screenshot do canvas (não fullPage). E **pergunta
  ao usuário quais telas** capturar em vez de fixar um número.
- **Convenção de nomes:** todas as skills passam a usar o prefixo `sw-` (systemweb) —
  evita colisão com skills de outros marketplaces. As 5 publicadas foram renomeadas:
  `frontend-component-kit`→`sw-frontend-component-kit`, `frontend-mockup-preview`→`sw-frontend-mockup-preview`,
  `git-commit`→`sw-git-commit`, `dead-code-scan`→`sw-dead-code-scan`, `skill-test`→`sw-skill-test`.
  ⚠️ Muda o comando de install (ex.: `/plugin install sw-git-commit@ai-marketplace`).
  Cross-references entre skills atualizadas; caminhos internos da `sw-study-buddy` corrigidos.
- `frontend-component-kit` (v0.1.1) e `frontend-mockup-preview` (v0.1.2): nova regra
  "toda pergunta via `AskUserQuestion`" (menu clicável, sem pergunta em texto solto).
- `scripts/sync_skill.py`: o sync agora **preserva a categoria** já registrada quando
  `CATEGORY=` não é informado (antes revertia para o default `development`).

### Adicionado
- `sw-cluster-audit` (v0.2.0): **relatório muito mais rico e amigável.** Além dos fatos, agora traz:
  **resumo executivo** (o agente explica *por que* o veredito), **notas por dimensão**
  (Segurança/Disponibilidade/Higiene, determinísticas), **recomendações priorizadas**
  (impacto/esforço), **pontos fortes × fracos**, **findings agrupados por regra e explicados**
  ("o que é / por que importa / como corrigir" em vez de tabela crua), **análise por componente**,
  **top ofensores** e **diff com a auditoria anterior** (resolvidos/novos). Template redesenhado
  (self-contained). +5 módulos/testes (métricas, rule_meta), 68 testes. Validado no cluster real.
- Skill publicada: **`sw-cluster-audit`** (v0.1.0, categoria `development`) — auditoria **READ-ONLY**
  de cluster Docker (context/Swarm) → relatório técnico **HTML + PDF** (opt-in) em `docs/infra/`.
  Coleta via **allowlist `(noun,verb)`**, **redação field-allowlist positiva** (zero valor de
  secret/env), **findings de segurança por regra determinística** (privileged, docker.sock, porta
  0.0.0.0, imagem sem digest, root), **análise por componente app-aware** (detecta Traefik/filas/
  bancos/cache e o agente analisa cada um — roteamento, HA, exposição), **degradação honesta** e
  `.gitignore` não-opcional. **7 fitness functions verificáveis**, 63 testes. Desenhada via
  `sw-brainstorming` → `sw-plan` (spec e plano em `docs/specs/` e `docs/plans/`).
- Estrutura inicial do marketplace (formato oficial de plugins do Claude Code).
- Script `scripts/sync_skill.py` + `Makefile`: sync `local → repo`, `import`
  (`repo → local`), `list`, `remove`, `readme`.
- Skills publicadas: `frontend-component-kit` e `frontend-mockup-preview` (categoria `design`).
- Skill publicada: `sw-study-buddy` (v0.1.0, categoria `productivity`) — tutor de estudos de
  tecnologia (modos Aprender/Explicar/Praticar, apostila viva em HTML, progresso). Ao iniciar,
  oferece buscar novidades/mudanças recentes do tema na internet (foco "o que mudou", datado).
- Skill publicada: `sw-design-studio` (v0.1.0, categoria `design`) — diretor de design
  interativo: decide a direção visual (8 eixos) fugindo dos clichês de IA, com modo de condução
  (guiado/autopilot/híbrido), modo didático (nomeia técnicas + glossário), e usa o design system
  existente como base. Combina só com skills de design (mockup-preview, component-kit).
- Skill publicada: `sw-code-review` (v0.1.0, categoria `development`) — review profundo
  language-agnostic com princípio "zero falso positivo": roda linters/typecheckers reais
  (Step 4c), verificação adversarial + nível de confiança (Step 5.5), supressão de FP, modo PR,
  RBAC/info-disclosure/typo-cross-file/cross-repo. Catálogo de patterns em references/patterns.md.
- Skills publicadas: `sw-brainstorming` e `sw-writing-plans` (v0.1.0, categoria `productivity`) —
  pipeline de design→plano: brainstorming (o quê, com resumo não-técnico opcional) e
  writing-plans (como + executar, com tipos/qualidade de teste, aprovação de plano e commit nos checkpoints).
- Skills publicadas: `dead-code-scan` e `skill-test` (v0.1.0, categoria `development`) —
  varredura de código morto com modelo de confiança; e teste leve de skills (comportamento + disparo).
- Skill publicada: `git-commit` (v0.1.0, categoria `development`) — split em Conventional
  Commits, com split por hunk (Rule E), fallback p/ repo sem histórico, tratamento de hook
  que reformata, `Co-Authored-By` conforme convenção e toda decisão via `AskUserQuestion`.
- Gate de segurança `scripts/scan_secrets.py` + git hooks `pre-commit`/`pre-push`
  (`make hooks` / `make check`): bloqueia commit/push com credenciais ou dados pessoais.
- `CLAUDE.md` com as regras do projeto.
- Documentação PT-BR: README, CONTRIBUTING e `docs/estrutura.md`.
