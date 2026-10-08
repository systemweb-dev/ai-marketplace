# Changelog

Todas as mudanças relevantes deste marketplace são registradas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versões de cada skill seguem [SemVer](https://semver.org/lang/pt-BR/) no
`plugin.json` correspondente.

## [Não publicado]

### Adicionado
- `sw-codebase-guide` (v0.9.0): **a skill deixou de depender do agente adivinhar por onde
  começar a rastrear.** O `SKILL.md` declarava *"a skill não detecta entrypoint"* enquanto a
  seção `superficie` já listava rota, job, comando e migration. O que faltava era usá-los
  para **propor** — e escolher errado é caro, porque o percurso é a parte do documento que
  mais custa a escrever.

  - A nova seção `percursos` do inventário ordena as entradas pelo número de **papéis
    distintos** que alcançam, não pelo número de arquivos: uma entrada que toca
    `request · service · model · enum` é fatia vertical; uma que toca trinta modelos é
    listagem. Cada candidato vem com o `termo` da funcionalidade, ligando os dois eixos de
    recorte.
  - **Ranquear por "aplicações atravessadas" seria inútil, e isso foi medido antes de
    escrever o módulo:** nenhuma das 49 entradas de um monorepo real atravessava aplicação
    pelo import, porque a travessia é por HTTP. O limite sai impresso junto da lista, para o
    leitor não concluir que o caminho acaba ali.
  - **17 das 49 entradas não alcançam arquivo nenhum pelo import**, e esse número agora vai
    para o documento: é o tamanho do ponto cego, e quem lê precisa saber disso antes de
    confiar no grafo para rastrear.

### Corrigido
- **O harness de provas de mutação mentiu uma segunda vez, por outro motivo.** Dois arquivos
  de teste passados como uma string só viraram um caminho inexistente; o pytest saiu com
  erro de uso, a saída continha a palavra "error", e as oito mutações foram marcadas como
  pegas sem que um único teste tivesse rodado. Agora só o código de saída **1** (um teste
  falhou) ou um timeout contam como prova — erro de uso, erro de coleta e "nenhum teste
  coletado" saem como `INCONCLUSIVO`. As oito provas foram refeitas: 8/8, com a mutação do
  ciclo de import saindo em timeout, que é a prova certa.

### Adicionado
- `sw-codebase-guide` (v0.8.0): **as perguntas em aberto passam a sair do que foi medido.**
  A skill declara essa seção como o entregável de maior valor — é a pauta da conversa com
  quem conhece o sistema —, e ela eram **três strings fixas** mais as `lacuna` do agente,
  enquanto o `julgamento` já tinha medido um arquivo com 55 dependentes e nenhum teste, um
  `.env` versionado e um par que muda junto 38 vezes. Nenhum desses fatos virava pergunta.

  - *"`constants/index.js` tem 55 dependentes e mudou 35 vezes: quem mexe nele hoje, e como
    essa pessoa sabe que não quebrou nada?"* é pauta de reunião. *"Estas pastas ainda são
    usadas?"* é formulário — e esta agora só sai quando não há pergunta específica.
  - **O par que muda junto e não se importa.** Dois arquivos que o histórico mostra mudando
    no mesmo commit, acima de um piso, e sem nenhuma aresta de import entre eles: é o
    acoplamento que o grafo não vê — rota em string, injeção de dependência, reflexão,
    template. Num projeto real ele achou sozinho o par mais acoplado do projeto. A pergunta
    só nasce nas linguagens cuja resolução passou do piso: num grafo pela metade, "não há
    aresta" quer dizer "não medi", e a pergunta viria de uma cegueira da skill.
  - **Nenhuma pergunta afirma.** Há teste rodando a lista `PROIBIDAS` do `montar.py` contra
    toda pergunta derivada: quem lê de relance guarda a frase e esquece o ponto de
    interrogação, e a pergunta sobre arquivo parado é a mais fácil de errar.
  - As perguntas saem **nos dois documentos**. O bloco do HTML já se anunciava como "a pauta
    da conversa com quem conhece o sistema" e entregava metade dela.

- `sw-codebase-guide`: **guarda de paridade entre os dois emissores.** `leia-me.md` e
  `leia-me.html` nascem do mesmo material e nenhum é conversão do outro — é decisão de
  desenho, e o preço é que nada impedia os dois de contarem histórias diferentes. Já tinha
  acontecido duas vezes, as duas achadas por olho humano. Agora um registro declara, para
  cada um dos 19 blocos do HTML, onde está o gêmeo — ou `None` **com o motivo**. Bloco novo
  falha o teste até alguém declarar a decisão, e seis testes de comportamento comparam o
  conteúdo dos documentos gerados, com a divergência histórica reencenada como prova.

### Corrigido
- **O harness de provas de mutação podia marcar "pega" uma mutação que sobreviveu.** Python
  valida bytecode por (mtime em segundos, tamanho do fonte); duas mutações que removem a
  mesma substring produzem arquivos do mesmo tamanho, e rodando no mesmo segundo a segunda
  reusava o `.pyc` da primeira. O defeito escondia uma lacuna real de teste. O harness agora
  roda com `PYTHONDONTWRITEBYTECODE` **e** apaga os `__pycache__` antes de cada rodada, exige
  que o padrão da mutação seja único no arquivo, e restaura em `finally`. Todas as provas
  desta sessão foram refeitas com ele: 13/13, 6/6 e 4/4.

### Adicionado
- `sw-codebase-guide` (v0.7.0): **recorte por funcionalidade — dizer o *quê*, não o *onde*.**
  O `--area` recorta por caminho, e quem acabou de receber um projeto não pergunta por
  `src/app/(app)`: pergunta pelo cadastro, pelo faturamento, pelo funil. O nome dessas coisas
  já está escrito no código, só não estava reunido em lugar nenhum.

  - **A hipótese foi medida antes de virar código**, em quatro projetos reais (um monorepo
    PHP+Vue, um portal de notícias, um CRM Next.js e uma API PHP): *uma funcionalidade é um
    nome que aparece em mais de um papel*. A extração devolveu nomes que alguém reconhece —
    `cadastro`, `cobranca`, `funil`, `leads`, `relatorio` — e quatro defeitos, cada um virou
    uma regra: `[id]` de
    roteador não é nome; **teste não conta como papel** (é o espelho do arquivo, não uma
    segunda camada); `middleware` + `rotas` sozinhos declaram **área**, não funcionalidade; e
    `index` é barril.
  - **O recorte sai em três grupos** — núcleo (leva o nome), alcance (o núcleo importa e
    quase ninguém de fora usa) e **compartilhado** (o núcleo importa e o resto do sistema
    também). O terceiro é o que paga o recorte: medindo um cadastro real, o arquivo mais
    importante da fatia era o mais compartilhado — o helper onde mora a regra do formulário,
    com 29 importadores de fora. Deixá-lo de fora perderia a regra; chamá-lo de "parte da
    funcionalidade" seria mentira. Ele entra, e o documento imprime a conta.
  - **Termo que pega o projeto inteiro é declarado área.** O termo mais largo do projeto
    medido levava 148 de 760 arquivos; o documento diz isso em vez de entregar 197 arquivos
    chamando-os de uma funcionalidade.
  - **Os quatro filtros de recorte viraram um objeto só** (`lib/recorte.py`). Eram quatro
    comparações de prefixo escritas quatro vezes — uma delas comparava `area='api'` com
    `app/X.php` e zerava a co-mudança sem avisar —, e três das quatro só sabiam dizer "área",
    de modo que uma rodada por funcionalidade sairia anunciando o projeto inteiro.

### Corrigido
- `sw-codebase-guide` (v0.7.1): **a frase do recorte foi escrita supondo número positivo.**
  Rodando o recorte novo num framework de 46 arquivos que eu nunca tinha visto — com a suíte
  verde —, o bloco saiu dizendo *"**0** arquivos a mais o núcleo importa, e quase ninguém de
  fora usa"*. Além de absurdo, escondia o fato maior: zero nos dois grupos significa que o
  núcleo **não importa nada fora de si**, que é uma coisa a dizer, não uma a calar. Os três
  ramos agora têm frase própria e teste, com prova de mutação em cada um.

  Vale registrar o que o teste provou de passagem: num framework o menu saiu com **um**
  candidato, e é o certo — framework não tem funcionalidade de produto. O critério não
  enche a lista para parecer útil.
- `sw-codebase-guide`: **um teste que podia travar a máquina.** Os testes dos limiares
  dimensionavam a fixture pela constante de produção (`range(TETO_COMPARTILHADO + 1)`). Numa
  prova de mutação que levou o teto a `10**9`, o teste tentou alocar um bilhão de strings e
  derrubou a sessão duas vezes. Os limiares agora são parâmetro do `recortar`, com o padrão
  declarado no módulo: o limiar se prova com teto 2 e três arquivos. Dois testes continuam
  usando o teto real — é assim que provam que o padrão segue ligado — e uma guarda no módulo
  de teste falha em uma linha, em 0,05s, se alguém puser ali um número grande demais para
  dimensionar fixture.

### Adicionado
- `sw-codebase-guide` (v0.6.0): **o percurso virou trilha, e o arquivo de cada passo aparece
  na página.** O defeito era quieto: a `evidencia` do percurso era validada contra o projeto,
  caminho por caminho, e nenhum dos dois emissores a imprimia. Quem lia recebia a história de
  ponta a ponta e tinha que ir caçar os arquivos no relatório técnico — que é exatamente o
  trabalho que o documento existe para poupar.

  - **Um bloco de `percurso` deixou de ser parágrafo e virou PASSO.** Ele declara `onde` roda,
    numa lista fechada de cinco camadas — `navegador · servidor · fila · banco · externo`.
    Camada inventada é recusada com a lista na mensagem: camada livre reabriria a prosa pela
    porta dos fundos, e a trilha não teria onde pôr o passo.
  - **A travessia de fronteira não se declara: ela é derivada** de `onde` mudar entre dois
    passos consecutivos, e o documento imprime `navegador → servidor` entre eles. Declarar
    abriria a porta para afirmar uma travessia que os dados não mostram. Atravessar aplicação
    é o evento mais caro para quem acabou de receber o projeto, e era o que a prosa corrida
    escondia melhor — ficava numa oração subordinada no meio do parágrafo.
  - **O desenho foi escolhido vendo**, em preview com três variações que diferiam de verdade
    (trilha · camadas agrupadas · tabela densa). A trilha venceu porque é a única em que a
    fronteira *interrompe* o fio em vez de ser mais uma linha. Dois achados saíram do preview
    e não sairiam da descrição: a borda lateral grossa que eu usava para marcar fronteira é
    enfeite padrão de aviso (virou fio inteiro com fundo tingido), e no tema brutalista
    `--acento` e `--alerta` são a **mesma** tinta — lá a camada marca com o preto do fio, e o
    vermelho fica reservado para fronteira e lacuna, senão "servidor" e "externo" se liam
    igual.
  - **O salto continua no passo a que pertence.** A regra é velha e a mudança de layout não
    podia derrubá-la: salto escondido numa nota de rodapé é o erro mais caro que este
    documento pode cometer.
  - 13 testes novos em `tests/test_percurso.py`, com cinco provas de mutação — tirar a
    validação da camada, nunca derivar fronteira, marcá-la no primeiro passo, parar de
    imprimir o arquivo e ordenar as camadas por alfabeto. As cinco foram pegas.

### Corrigido
- `sw-codebase-guide` (v0.5.2): **oito defeitos achados por um agente que usou a skill lendo
  só o `SKILL.md`.** Era o teste que faltava: todas as execuções anteriores foram feitas por
  quem conhecia o código por dentro e preenchia de cabeça o que o documento não dissesse.
  Proibido de abrir os scripts, um agente seguiu o fluxo até o fim — e foi onde ele hesitou
  que apareceu o que importa.

  - **A skill lia `.claude/CLAUDE.md` e depois recusava citá-lo como evidência.** A pasta é
    podada da árvore, e a guarda só conhecia `caminhos_do_projeto` — então a mensagem dizia
    *"evidência não existe no projeto"* sobre um arquivo que o inventário tinha acabado de
    ler, e que constava nele duas vezes. Numa skill cujo valor é ler o `.claude/` "onde mora a
    única documentação de muitos projetos", isso é a regra brigando consigo mesma.
  - **O `SKILL.md` mandava não escrever o percurso em "o projeto todo"**, enquanto a tabela da
    narrativa o exige como uma das quatro partes. Obedecer produzia no documento a frase *"a
    interpretação não escreveu esta parte"* — o defeito que a skill avisa para evitar. Agora
    o percurso é obrigatório sempre; o que muda sem recorte é a ambição.
  - **"Leia os arquivos que o inventário aponta como centrais"** — e nenhum campo se chama
    central. O documento agora diz onde olhar, em ordem.
  - **A co-mudança citava 25 pares com arquivos que não existem mais**, porque o `git log`
    devolve caminho histórico. O leitor ia procurá-los. Agora o emissor filtra e **declara
    quantos** ficaram de fora; o inventário continua guardando o fato bruto.
  - **Caminho com acento saía em octal** (`"Documenta\303\247\303\243o.txt"`): faltava
    `core.quotepath=false` nas chamadas ao git.
  - **As afirmações eram reordenadas alfabeticamente**, e a frase mais importante de uma seção
    caiu em último lugar por começar com "É". Quem escreve a interpretação ordena por
    importância; o emissor não pode desfazer isso.
  - **HTML e Markdown discordavam** sobre a parte não escrita: um omitia, o outro avisava.
  - **O rótulo de confiança saía `[deducao]` em dois blocos e `[dedução]` num terceiro.**

- `sw-infra-audit` (v0.16.1): **o motivo com dois exporters se lia como um nome de produto.**
  Visto num relatório real: *"o exporter cadvisor, traefik não expõe o dado desta pergunta"* —
  correto no conteúdo, e lido como se `cadvisor, traefik` fosse um produto só. Agora o plural
  concorda e a lista é ligada por "e": *"os exporters cadvisor e traefik não expõem"*.

- `sw-codebase-guide` (v0.5.1): **seis defeitos achados rodando a skill num projeto que ela
  nunca tinha visto** — um monorepo de cinco repositórios git, com PHP, Node e um invólucro
  Android. Todos apareceram na primeira tela ou na leitura do documento; nenhum na suíte.

  - **O menu de escopo oferecia a pasta de documentação.** Oito das doze áreas eram subpastas
    de `docs/` — `docs/marketing`, `docs/product`, `docs/compliance` —, e `docs/product` tinha
    47 arquivos e **zero** código. O menu pergunta qual parte do SISTEMA documentar, então ele
    passou a pesar por arquivo de código: doze entradas viraram quatro.
  - **`require 'vendor/autoload.php'` contava como import pendurado.** São 62 ocorrências do
    mesmo autoloader num projeto, e `vendor/` é podado de propósito — indexá-lo custaria a
    varredura inteira. Isso é dependência externa, não falha de medição, e contá-lo errado
    derrubava a taxa de PHP de **99% para 91%**.
  - **Uma imagem aparecia entre os arquivos mais importados do JavaScript.** A aresta é real e
    fica no grafo, mas o ranking existe para mostrar acoplamento de código — e o `.png` ocupava
    uma das quinze vagas.
  - **O documento perguntava o propósito do sistema três parágrafos depois de respondê-lo.** A
    guarda que suprime a pergunta fixa contava só `fato` e `declarado`; foi escrita quando
    propósito só podia vir de fonte textual, regra que caiu no spike da v0.2.0. Hoje a resposta
    mais comum é uma dedução de evidências convergentes, ou a narrativa com a citação literal.
  - **"1 pessoa commitaram"** e "12 semanas parado" — concordância no bloco de decisão.

- `sw-codebase-guide` (v0.5.0): **o que alguém responde passa a sobreviver à regeração.** Até
  aqui os três artefatos eram descartáveis por desenho — o inventário se refaz, a
  interpretação se reescreve, o documento se monta de novo —, e com eles ia embora tudo que
  uma pessoa tivesse confirmado. Rodar a skill de novo em três meses fazia as mesmas perguntas
  que já tinham sido respondidas, que é exatamente como um documento gerado perde
  credibilidade.

  O `knowledge.toml` é o **único arquivo da skill que não se regenera**, e por isso tem o
  formato mais fechado de todos: quem grava é o `gravar.py`, com escrita **atômica** — o texto
  novo é montado, conferido como TOML em memória, e só então substitui o arquivo. Anexar e
  validar depois deixava um bloco quebrado dentro de um arquivo que ninguém pode refazer, e
  aí a informação de todo mundo fica inacessível por causa de uma resposta malformada.

  Isso cria o **quinto nível de confiança**. Os outros quatro — `fato`, `declarado`, `deducao`
  e `lacuna` — derivam do repositório; `confirmado` é o único cujo lastro é uma pessoa, e por
  isso ele nunca aparece sem o **nome dela e a data** ao lado. Resposta sem nome não dá para
  conferir depois.

  **A resposta envelhece por evidência, não por cronômetro.** O inventário passou a carregar a
  data da última mudança de cada arquivo: respondido em outubro, arquivo mexido em dezembro, a
  resposta aparece com aviso em vez de ser repetida como verdade. Ela não vira falsa — vira
  suspeita, e o documento diz isso.

  O que foi respondido **sai** da lista de perguntas e passa a constar em "já perguntamos". O
  documento melhora a cada rodada, e a resposta continua conferível.

  E a promessa mais forte da skill ganhou a sua formulação exata: **ela** nunca afirma ausência
  de dependentes, porque o grafo não pode provar isso; uma **pessoa** pode, porque sabe o que o
  grafo não vê. O que separa as duas é a atribuição, e há um teste que exige isso linha a
  linha: frase de ausência no documento só vale com nome e data ao lado.

- `sw-codebase-guide` (v0.4.0): **a skill passou a julgar** — e esta é a primeira versão em
  que ela opina sobre o projeto, não só o descreve. São as quatro perguntas de quem recebe
  código que ninguém da casa conhece, e cada uma tem uma forma só: **sinal medido, limiar
  escrito, e a frase do que ele não diz**. Nota não existe; número único vira meta, e meta
  vira teatro.

  **Onde é mais caro errar** — os três sinais *juntos*: mais de 5 arquivos importando, mais de
  10 commits de histórico, e nenhum teste de mesmo nome e mesma extensão. Isoladamente nenhum
  diz nada, e é a coincidência que descreve perigo. Num projeto real isso aponta
  `constants/index.js` com 55 dependentes e 35 commits, sem teste.

  **Risco visível** — só o que se vê sem rede e sem executar nada: `.env` **versionado** (a
  diferença entre "existe no disco", que é normal, e "está no git", que é credencial
  publicada, é uma consulta ao git) e variável com cara de credencial que o `.env.example` não
  declara. O valor nunca é lido: os achados falam de nome de arquivo e nome de chave.

  **Ninguém parece usar — ainda é usado?** Arquivo que import nenhum alcança e que ninguém
  toca há mais de um ano. Sai como **pergunta**, nunca como veredito, porque "está morto" é
  literalmente a frase que a skill promete não dizer. Três travas: só nas linguagens acima do
  piso de 70% de resolução, só acima de um ano parado, e sem os papéis que o framework
  instancia por convenção — num projeto real o terceiro candidato era um controller alcançado
  por rota-em-string, e lista cheia de controller é pior que lista nenhuma. Com as travas, o
  monorepo de calibração saiu de 14 candidatos para 2, e os dois foram conferidos à mão: um
  componente Vue que só aparece em comentários, e um arquivo de configuração que ninguém
  menciona.

  **Vale manter ou reescrever?** A skill **não responde**, e isso é desenho: a resposta depende
  de quanto custa reescrever e do que o negócio depende, e o código não contém nenhum dos dois.
  Ela põe a mesa — fator ônibus, idade, tempo parado, cobertura, tamanho, o que foi medido — e
  diz por escrito qual é o número que falta.

  O `inventory.json` ganhou a seção `julgamento`, calculada por último porque lê todas as
  outras, e o `historia.py` ganhou `por_arquivo` (data da última mudança e contagem de commits,
  numa passada só) e `rastreados` (o que o git controla).

### Corrigido
- `sw-codebase-guide` (v0.4.0): **o extrator de PHP passou a ler `require` e `include`** com
  caminho literal. Sem isso, todo arquivo carregado assim parecia não ter ninguém apontando
  para ele — e num projeto real o front controller (`www/index.php`) e o `config/Defines.php`
  apareciam como candidatos a código morto, que é o falso positivo mais caro que essa lista
  pode ter.

- `sw-codebase-guide` (v0.3.0): **o grafo de import passou a existir para PHP, JavaScript,
  TypeScript e Vue** — e a seção "o que depende do quê", que era lacuna nessas stacks, agora
  diz quem importa quem. Medido nos projetos de calibração: **98% a 100%** dos imports
  internos resolvidos em JS e PHP, com o grafo de Python **idêntico ao anterior**, aresta por
  aresta.

  A decisão que faz isso funcionar é não acreditar na configuração. Resolver a string do
  import em arquivo exigiria ler PSR-4, `tsconfig.paths` e o apelido do bundler — e num
  projeto real o apelido mora num `vue.config.js`, que é **JavaScript executando**, não dado.
  A skill resolve pelos **arquivos que existem**: casa o import contra o índice de sufixos do
  projeto, e sufixo único vira aresta. Numa segunda passada, as bases já provadas por cinco
  imports desempatam o que ficou ambíguo — e isso **redescobriu os quatro apelidos declarados**
  naquele `vue.config.js` sem abrir o arquivo. A configuração entra só como atalho, e só
  depois de conferida contra o disco: mapeamento que aponta para pasta inexistente é
  descartado.

  **Sintaxe é por linguagem, resolução é uma só.** Cada `lib/linguagens/<x>.py` devolve as
  strings de import, classifica cada uma em `relativo | qualificado | nome_puro` e declara o
  que a resolução precisa saber sem perguntar — extensões, builtins, arquivo de pasta, se nome
  puro pode ser interno, onde mora a configuração. Nenhuma dessas sete peças toca o disco, e
  um teste confere que o resolvedor não contém nome de linguagem nenhum: acrescentar uma
  linguagem custa um extrator pequeno.

  **Cada execução publica a própria taxa de resolução**, em sete números absolutos e não em
  percentual — é o resolvedor que decide o que é "externo", e inflar esse balde inflaria a
  fração. Abaixo de **70%** numa linguagem, a seção de dependências dela volta a ser lacuna,
  porque ranking sobre metade do grafo tem cara de fato.

### Corrigido
- `sw-codebase-guide` (v0.3.0): **a lista por símbolo saiu, e o ranking é por arquivo.** Ela
  vinha de `mencoes` e casava PALAVRA, o que numa base em português devolvia `banco` e
  `caminho` com centenas de menções; com aresta real, "quem importa quem" tem resposta direta.
  O grafo textual continua no `inventory.json` para quem quiser olhar à mão, e o documento diz
  onde ele está.

  Quatro defeitos achados medindo, não lendo:

  - **nome puro vira externo por regra**, não por coincidência: `import 'server-only'` casaria
    com `tests/helpers/server-only.ts` — oito arestas erradas num projeto real. Mas a regra é
    do JavaScript: em Python `from pedido import X` é módulo local, e aplicá-la lá apagaria o
    grafo que já funciona. Por isso a linguagem **declara** qual dos dois vale;
  - **dependência externa não é falha de medição.** `collections/Counter` e
    `use SysWeb\Controller` eram contados como não resolvidos — o primeiro é stdlib, o segundo
    mora em `vendor/`, e nome de pacote do composer não é namespace do PHP. Isso levava a taxa
    do Python a 33% e a do PHP a 57%, com as arestas todas certas;
  - **backtracking catastrófico** numa expressão que aceitava quebra de linha: `(?:[^'";]|\n)*?`
    é alternância ambígua, porque classe negada já casa `\n`. Medido 0,56 s com 18 linhas de
    miolo e **36 s com 24** — e o gatilho é uma `interface` TypeScript sem ponto e vírgula, o
    padrão do formatador em projeto Vue. Um arquivo desses estourava sozinho o orçamento de
    60 s da varredura;
  - **import quebrado em várias linhas** não casava, e é a forma padrão assim que a linha passa
    da largura: 40 imports internos sumiam, sem erro, só ausentes.

  O `inventory.json` voltou a ser determinístico entre processos: as arestas eram concatenadas
  num laço sobre um `set`, cuja ordem muda por processo, e passava por acidente porque só uma
  linguagem gerava aresta.

- `sw-codebase-guide` (v0.2.0): **um segundo documento, para gente, ao lado do relatório
  técnico** — e o escopo escolhido na entrada, porque num projeto de 1.900 arquivos
  "documentar o projeto" e "documentar o cadastro de cliente" são documentos diferentes.

  `varrer.py --areas` imprime o menu de escopo e **não grava nada**; `--area <caminho>`
  recorta. O recorte tem três regras, uma por seção: árvore e superfície por prefixo; stack e
  ambiente por prefixo **mais o que é herdado de cima, marcado como tal**; história e menções
  por **uma ponta dentro** — porque o par que cruza a fronteira é justamente o valor da seção
  ("para mexer no funil você quase sempre mexe num componente que mora fora daqui").

  O `montar.py` passa a emitir também o `leia-me.md`, em quatro partes: *o que o produto faz*,
  *o percurso de uma funcionalidade*, *onde ficam as coisas* e *para mexer*. O `imprimir.py`
  gera o `leia-me.html` — arquivo único, sem nenhuma requisição de rede, com as fontes
  embutidas — e o PDF sob demanda. Três guardas recusam o processo inteiro, e nenhum dos dois
  documentos é escrito quando uma delas fala: **frase de ausência** ("nada depende disso" não
  existe neste documento), **trecho literal** (a citação tem que aparecer de fato na fonte) e
  **caminho inventado** (toda evidência tem que existir no projeto).

  Novo no inventário: `retrato` — quantas pessoas commitaram, quantos commits, idade e semanas
  parado —, `textos` (a única seção que carrega conteúdo, e por isso redigida linha a linha),
  `escopo` e `caminhos_do_projeto`. **Nunca zero no lugar de "não sei"**: sem git, o retrato
  vem `None` com o motivo, porque `0 autores` se lê como *ninguém mexe nisso* e `1` como *uma
  pessoa só*.

### Corrigido
- `sw-codebase-guide` (v0.2.0): **dez defeitos achados rodando a skill em dois projetos que
  ela nunca tinha visto** — um monorepo por justaposição (quatro repositórios git, nenhum na
  raiz) e um projeto PHP. Nenhum deles aparecia na suíte verde, e cinco têm a mesma causa: a
  regra *"desça um nível quando a raiz não tem git"* fora escrita uma vez **por consumidor**,
  então cada consumidor novo esquecia dela. Agora é um `subrepos()` só.

  - **Fonte textual só valia na raiz.** Os padrões estavam ancorados em `^`, e num monorepo o
    README de cada aplicação mora em `admin/`, `api/`, `website/`: seis READMEs na árvore,
    **zero** lidos. Como "propósito só com fonte textual" é regra da skill, a frase mais
    valiosa do documento virava lacuna por causa de um acento circunflexo. No projeto PHP o
    caso era outro e pior: a única documentação morava em `.claude/`, que é podada da árvore —
    agora ela é procurada à parte, e aquele projeto passou de 0 para 15 fontes.
  - **A seção `textos` ganhou teto** (32 arquivos, 384 KB). Desancorar os padrões fez a
    varredura engolir os dossiês de trabalho: 68 fontes e **1,4 MB** num arquivo que é
    commitado, 60 delas `plan.md` e `spec.md` de tarefas já entregues. O que não cabe continua
    na lista com o motivo, para quem lê abrir à mão.
  - **O menu de escopo anunciava `0 commits` nas seis áreas de um monorepo vivo**, e ordenava
    pela maior aplicação em vez da mais mexida. Não medido agora é `null`; zero medido segue
    zero.
  - **O documento dizia "não há repositório git aqui" ao lado de 782 commits de co-mudança**,
    porque o `retrato` era o único que não descia nos sub-repositórios. E o bloco carimbava
    NÃO APURADO sobre seis autores medidos: a lacuna ali não é ausência, é procedência.
  - **`**Não rastreado:** Não rastreado:`** — o emissor põe o rótulo e quem escreve usa a mesma
    palavra, que é a frase natural. Junto: *"Sem saltos: o percurso foi seguido sem buraco"*
    saía sob **cada** parágrafo, então a página negava buraco duas vezes antes de mostrar dois.
  - **A aba do navegador dizia "Guia do projeto"** em todo documento, e a manchete saiu com 207
    caracteres num projeto cuja primeira frase separa as orações com `:` e vírgula.
  - **O mesmo documento chamava um `.md` de código no cabeçalho e de "não é código" no bloco de
    arquivos maiores** — duas definições na mesma página, com o conjunto `ATIVOS` existindo em
    três cópias.
  - **A crase da prosa aparecia na tela**: só a citação literal passava pelo renderizador, e
    `` `Helper::isMinor` `` chegava ao leitor com as crases.

  Mudança de contrato: **só o primeiro bloco de `o-que-e` precisa citar**. A guarda confere que
  a citação *existe* na fonte, nunca que ela *sustenta* a frase — e exigir citação de todo
  bloco empurra quem escreve a pendurar um trecho verdadeiro e sem relação embaixo do
  parágrafo, que na tela aparece com cara de evidência. Pior que não citar. A frase mais
  valiosa costuma ser dedução de evidências convergentes de código, e agora ela pode ser
  escrita como é.

  **30 provas por mutação**, e quatro delas só mataram depois de consertar o *fixture*. A
  suíte foi de 95 para 206 testes.

### Corrigido
- `sw-codebase-guide` (v0.1.1): **a seção "O que depende do quê" virava ruído ilegível quando
  não havia grafo de import.** Num projeto Next.js real ela saía com 142 linhas assim:
  `export — import não medido, 266 menções textuais`, `banco — 205 menções`,
  `caminho — 159 menções`. Nenhum desses é símbolo: são nomes de arquivo (`export.ts`,
  `banco.tsx`) que o grafo textual casa como PALAVRA — e numa base em português `banco` e
  `caminho` aparecem às centenas sem haver relação de código, inclusive dentro de arquivos
  de documentação.

  Sem aresta de import, a seção passa a ser uma **lacuna com motivo** em seis linhas: diz que
  o acoplamento não foi medido para aquela stack, explica por que o grafo textual sozinho não
  vira afirmação, e aponta o `inventory.json` para quem quiser olhar à mão. O documento do
  projeto real caiu de 336 para 116 linhas.

  A regra por trás, que vale para o resto da skill: **quando a medição não existe, o lugar
  dela é uma lacuna com motivo — não uma aproximação ruidosa com um aviso em cima.** O aviso
  já estava lá, correto, e perdia: ninguém lê uma ressalva e depois duvida de 142 linhas, uma
  a uma. De quebra, a mesma coisa estava sendo dita três vezes — as cinco cegueiras do grafo,
  a indisponibilidade da stack e a lacuna —, e três avisos empilhados comunicam menos que um.

### Adicionado
- `sw-codebase-guide` (v0.1.0): **lê um projeto que você acabou de receber e escreve a
  documentação dele** em `docs/project/` — como entrar, o que depende do quê e o que o sistema
  faz, cada afirmação com o nível de confiança e a evidência, fechando com as perguntas que a
  skill não conseguiu responder.

  A decisão fundante é não entrevistar: quem roda a skill é exatamente quem acabou de receber o
  projeto e não sabe responder. Um script determinístico apura os fatos num `inventory.json`,
  o agente escreve a interpretação num arquivo próprio e um segundo script monta o documento —
  três artefatos com um escritor cada, para o inventário continuar regenerável e o documento
  dar diff. **Propósito só é afirmado com fonte textual citada** (README, ADR, mensagem de
  commit); sem fonte, vira pergunta em aberto, porque deduzir propósito de rota e modelo produz
  prosa plausível que o consultor leva ao cliente como se fosse apurada.

  Duas garantias são estruturais, não boa intenção. **Nenhum segredo sai:** de cada `.env` o
  inventário carrega só os NOMES das variáveis, extraídos na origem — contra 15 credenciais
  reais de um projeto, nenhuma vazou, e as 93 chaves entraram, que é a informação útil para
  quem vai subir o ambiente. **Ausência de dependentes nunca é afirmada:** o grafo de import não
  enxerga injeção de dependência, rota como string nem template, então "nada depende disso" não
  existe no documento — sai "N por import, M menções textuais", com a lista do que o grafo não
  vê anexada, e um conjunto de frases proibidas é testado contra o texto gerado.

  Rodou em seis projetos reais da casa antes de ser publicada, e foi isso que achou os defeitos
  que fixture nenhuma acharia: 210 arquivos Python saindo como "sem stack" por não haver
  `pyproject.toml`, 243 imports locais virando zero arestas porque o módulo era ancorado na raiz
  em vez da source root, e 782 commits em quatro sub-repositórios sendo reportados como "não há
  repositório git aqui" — monorepo por justaposição, que é o formato de um terço dos projetos
  testados.

  Limites desta versão, escritos na própria skill: grafo de import só para Python (as outras
  stacks aparecem como indisponíveis **com motivo**), superfície por convenção de caminho, sem
  conhecimento humano persistido entre execuções, sem recorte por área, sem HTML nem PDF, e sem
  extração de regra de negócio.

### Alterado
- `sw-infra-audit` (v0.16.0): **o papel de um componente passou a ser provado pela série que
  ele publica, não adivinhado pelo nome da imagem.** Era a última coisa na skill a violar o
  princípio que ela mesma documenta — nome de imagem mente com fork e tag genérica —, e a mais
  consequente: o papel decide quais perguntas o componente recebe.
  Um fork de cache que o catálogo de produtos não conhece pelo nome entra como `app` e sai
  `cache`, identificado pelo exporter do produto original, que o reconhece pela série. O
  relatório diz de onde veio cada papel, e quando a evidência contradiz a imagem ele diz isso:
  *"papel confirmado pelo exporter redis-exporter; a imagem sugeria app"*.
  O `produtos.toml` foi rebaixado de autoridade a palpite, e o filtro por papel da v0.14.0 saiu
  — a proteção que ele dava virou casamento de etiqueta, que é evidência e não heurística. O
  custo CAIU: a identificação passou a ser uma consulta por família por fonte, em vez de uma por
  pergunta, e o cache que o docstring prometia desde a v0.12.4 passou a funcionar de fato.
  Duas travas existem porque sem elas o papel sai errado em direções opostas: a família declara
  se a série dela PROVA papel (o exporter de container casa todo componente, porque a etiqueta
  dele é o nome do serviço), e o produto declara se é um exportador (o container do
  `postgres-exporter` casava a própria família e virava `banco`, enquanto o banco de verdade
  ficava sem identidade — perfeitamente invertido).
  Componente sem papel provado passou a contar como lacuna de medição: papel errado faz a
  pergunta errada, e isso é cegueira tanto quanto pergunta sem resposta.

- `sw-infra-audit`: **o último nome de produto saiu do código.** A configuração de roteamento
  só era legível para um proxy — `("traefik.",)` cravado na redação, e `k.endswith(".rule")`
  escrito em mais dois módulos, que nem sabiam que aquilo era sintaxe de produto. Agora o
  produto declara `[produto.rotas]` com o prefixo que sobrevive à redação e o sufixo que
  identifica a regra; acrescentar um proxy é um bloco de dados. De quebra ficou mais estrito:
  `endswith(".rule")` solto contava como rota qualquer label de terceiro terminada assim.
- `sw-infra-audit`: o vocabulário de `kind` estava escrito **três vezes**, sob **dois nomes**
  (`metrics.CRITICAL_PATH` e `impact.INGRESS`), e a terceira cópia já tinha derivado: faltava
  `api-gateway`, então um gateway com réplica única não contava como ponto único de falha ali,
  embora contasse nos outros dois. Mora num lugar só, em `lib/papel.py`, que já era o dono do
  vocabulário.

### Corrigido
- `sw-infra-audit`: `kind_do_caminho` **pulava produto sem `kind`**, então o bloco do
  `postgres-exporter` nem era considerado e `postgres` casava por substring — o exporter entrava
  no inventário como um banco, alimentando `metrics.STATEFUL` e `impact.CRITICAL_PATH`.
- `sw-infra-audit`: quatro papéis compartilhavam o rótulo "guarda" e o relatório saía com duas
  seções numeradas com o mesmo nome. Era invisível enquanto um fork de cache caía em `app`.

### Alterado
- `sw-infra-audit` (v0.15.0): **o que a skill sabe por nome de imagem saiu do código.** Três
  tabelas chaveadas por imagem viviam espalhadas — o tipo do serviço (`coletores/docker.py`),
  quem monta o `docker.sock` por desenho (`rules.py`) e os candidatos a fonte de métrica do
  `--sugerir` (`discover.py`). Acrescentar um produto exigia editar três listas em dois
  arquivos, e quem não soubesse disso editava uma. Agora um produto é um bloco em
  `references/produtos.toml`. A skill já prometia que "acrescentar um produto é escrever um
  arquivo"; era verdade do caminho de métrica e mentira do resto.
  Uma trava lê a árvore sintática e recusa nome de produto em literal de código — frase dirigida
  a quem lê o relatório continua liberada, valor de tabela não. E a classificação de cada
  produto conhecido ficou fixada em teste: a ordem dos blocos decide o empate no casamento por
  trecho, e reordenar não pode mudar o inventário em silêncio.

### Corrigido
- `sw-infra-audit` (v0.14.1): **o relatório imprimia o valor em cima do nome.** Na lista de
  consumidores por fila saía `notas4`, `web2ooks`, `emai0s`. A causa não era CSS feio: o
  renderizador falava um vocabulário de classes que o template não conhece. `.rk` é uma grade
  de quatro colunas que espera `ordinal · nome · trilho · valor`, e o renderizador emitia
  `lb/vl/bar` — o nome caía na coluna de 20px do ordinal e transbordava por cima do número.
- `sw-infra-audit`: **o mostrador não existia.** `.med`, `.anel`, `.arco`, `.agulha` e `.eixo`
  não tinham regra nenhuma no template: cinco `div` vazios. E o `<p class="faixa">` de dentro
  dele herdava a regra da **faixa de triagem**, que em impressão força página nova — todo
  cartão com tolerância declarada partia ao meio numa quebra de página. `perguntas.py` promete
  que "só quem declara faixa vira mostrador no relatório"; a promessa não era cumprida.
- `sw-infra-audit`: **o arco do mostrador mentia.** Desenhado em três partes iguais, ele dizia
  que 1000 ms ainda era bom numa pergunta cujo `bom_ate` é 700. As marcas agora saem da
  tolerância declarada, nos dois sentidos — num relatório cuja regra é "número sem fonte não
  existe", faixa colorida sem tolerância é número com fonte inventada.
- `sw-infra-audit`: **as três bolinhas da legenda do mapa eram invisíveis.** O renderizador
  escrevia `var(--verde)`, `var(--ambar)` e `var(--vermelho)`; o template define `--ok`,
  `--warn` e `--crit`. Variável que não existe resolve para vazio e leva a propriedade junto.
- `sw-infra-audit`: a legenda das camadas saía **em quatro colunas, com um dois-pontos solto**
  — o parágrafo usava `.nota`, que é um bloco com ícone (`display:flex`), e cada `<b>` virava
  uma coluna. E o bloco "o que falta declarar" colava rótulo e número
  (`3 perguntas sem respostacobertura 70%`), pelo mesmo motivo das classes acima.
- `sw-infra-audit`: a identificação de família fazia **duas consultas onde uma basta**. A
  segunda confirmava `count(serie{etiqueta="<nome>"})` depois de a primeira já ter devolvido os
  valores que a etiqueta tem — mesma série, mesmo instante, mesma fonte. Voltando vazia, o
  adaptador caía no ramo de "nenhum valor casa com este componente" e o relatório afirmava o
  contrário do que a fonte tinha acabado de responder, com o valor exato na mão.

### Adicionado
- `sw-infra-audit`: duas travas na **junta entre o renderizador e o template**, que é onde todo
  defeito acima nasceu: nenhuma classe emitida pode ficar sem regra, e nenhuma variável CSS
  referenciada pode ficar sem definição. Trinta e seis classes estavam sem regra. A trava não
  alcança o caso em que a classe tem regra *noutro contexto* — esse só aparece renderizando e
  olhando, e foi assim que os desta rodada apareceram.

### Adicionado
- `sw-infra-audit` (v0.14.0): **o papel `fila` deixou de exigir credencial.** Até aqui a única
  fonte era a API de administração do broker, com usuário e senha; quem tem o exporter no
  Prometheus e não quer criar usuário ficava com `sem dados`. Uma pergunta em forma de lista
  passou a aceitar itens de **vários campos**, com uma consulta por campo, juntas pela etiqueta
  declarada em `chave` — é o que permite um limiar comparar dois campos do mesmo item
  (`consumidores == 0 e prontas > 0`), que uma consulta PromQL sozinha não consegue devolver.
  Com as duas fontes declaradas, a mais específica vence e a pergunta é respondida **uma vez**.
  O carregador recusa a família que responda pergunta com limiar **sem medir os campos que o
  limiar compara**: sem essa trava o achado nunca dispararia, com a suíte toda verde.

### Corrigido
- `sw-infra-audit`: **dois componentes recebiam o MESMO número, cada um carimbado como se fosse
  dele.** O adaptador supunha que o valor da etiqueta do seletor era o nome do serviço no
  Swarm — verdade para o exporter de container, quase nunca para `job`, que vale o que o scrape
  config disser. Agora os valores são **descobertos** e casados com o componente por igualdade
  ou por composição (`<stack>_<serviço>`), nunca por substring solta: `db` dentro de `mariadb`
  atribuiria a medida do banco errado. Não casando, com um valor só a resposta sai do exporter
  inteiro e a fonte **diz isso**; com vários, vira `sem dados`, porque o número sem filtro
  seria a soma de todos.
- `sw-infra-audit`: **um banco apontando para o mesmo Prometheus do proxy era identificado como
  o proxy.** A série do proxy existe naquele Prometheus, afinal. A família passou a só concorrer
  se responde pergunta **do papel** daquele componente — o prefixo do id da pergunta é o que
  liga família a papel, sem nome de produto no código.
- `sw-infra-audit`: **`inf` numa pontuação derrubava a capa inteira**, e `NaN` saía como a
  MELHOR nota possível. `round(inf)` levanta OverflowError, que o `except` da nota não pegava; e
  `min(100, nan)` devolve 100, porque toda comparação com NaN é falsa. Na mesma varredura:
  `timeout = nan` no `config.toml` — que é TOML válido — derrubava a coleta no meio, com uma
  mensagem que não citava configuração nenhuma. As duas foram achadas por um teste que percorre
  a árvore sintática do pacote e cobra filtro de NaN de **todo** `float()` que possa chegar ao
  relatório; é a terceira vez que um conversor novo sem filtro mata a gravação do `report.json`,
  e as duas primeiras só apareceram rodando contra infraestrutura real.

### Removido
- `sw-infra-audit`: **`lib/enrich.py` foi aposentado** — uma segunda coleta, com uma tabela de
  consultas escrita no código, falando com o MESMO Prometheus para obter os MESMOS números que
  o catálogo de famílias já obtém. Sobreviveu tanto tempo porque o único consumidor dela era o
  renderizador anterior, que `build()` recusa desde que o relatório virou v3: dois caminhos, um
  deles cego. As consultas viraram arquivo de família (o exporter de container e o do broker
  AMQP); a sonda do alvo passou a ser a do próprio adaptador. Com isso, `metricas_url` passou a
  ser **a API de um Prometheus**, e não um `/metrics` cru — as perguntas são consultas com
  janela, que um raspão instantâneo não tem onde avaliar.

### Corrigido
- `sw-infra-audit`: **o relatório assinava 🟢 num cluster que ele não conseguiu medir.** Numa
  rodada real o mesmo cluster passou de 🔴 para 🟢 sem nada ter melhorado: a variável com a
  senha do broker não estava no ambiente, a pergunta que produz `fila_sem_consumidor` não foi
  respondida, nenhum achado nasceu e não havia o que agravar. A skill prega "não consegui ver
  ≠ está ruim"; o inverso, **"não consegui ver ≠ está bom"**, estava desprotegido. Agora
  pergunta com `limiar` sem resposta impede o 🟢 (teto, nunca piso — cegueira não produz 🔴) e o
  relatório diz qual componente, qual pergunta e qual motivo. Lista vazia numa pergunta com
  limiar deixou de contar como resposta: era a mesma cegueira por outra porta.

### Adicionado
- `sw-infra-audit` (v0.11.0): **o relatório passou a ser organizado por AÇÃO, não por
  gravidade.** Quem recebia "107 médios" tinha de traduzir aquilo sozinho em "o que eu faço
  hoje"; agora a pergunta já vem respondida em três faixas — **Agir agora** (crítico e alto),
  **Programar** (médio) e **Registrar e seguir** (baixo e informativo) —, e a faixa é o título
  da seção. A capa abre com uma **nota de estabilidade** derivada das dimensões por regra, e
  não escrita pelo agente: título reinventado a cada rodada torna duas auditorias
  incomparáveis. A triagem e a nota vivem em `lib/triagem.py` e `lib/nota.py`, como lógica
  pura — ordenar e contar achado não precisa de HTML para ser verificado —, com 25 testes e
  prova por mutação em cada trava.
- `sw-infra-audit`: o relatório virou **A4 paisagem** (1070px de conteúdo, 44% mais largura
  que o retrato) com as três fontes embutidas em **base64** (96 KB), porque o PDF é gerado por
  um Chromium sem rede e `@font-face` apontando para fora sairia com a fonte do sistema. As
  três são variáveis e OFL 1.1; as licenças viajam junto em
  `assets/report-template/fontes/`. Faltando um arquivo, o relatório sai com fonte de sistema
  em vez de não sair.
- `sw-infra-audit`: **a higiene passou a ser a média das quatro práticas que ela mede**
  (fixadas, não-root, com limite, com healthcheck) em vez de só `nonroot_pct`. Uma dimensão de
  quatro medidas que exibe uma delas como nota não descreve a dimensão.

### Corrigido
- `sw-infra-audit`: **o índice prometia seção que não existia.** Faixa sem achado nenhum
  continuava listada com link, e no PDF o clique não levava a lugar nenhum. Agora só vira link
  a faixa que foi desenhada — e há uma trava que confere, no HTML gerado, que todo `href`
  interno tem destino e que nenhuma âncora se repete. A trava pegou o defeito na primeira
  execução.
- `sw-infra-audit`: **tabela dentro de cartão voltou a ter a primeira letra comida.** A regra
  genérica `table{}` dá raio e `overflow:hidden` a toda tabela, e o canto arredondado cortava o
  "N" de "NOME". É o mesmo defeito que já tinha teste; o CSS novo tinha nascido sem a regra que
  o anula.
- `sw-git-commit` (v0.1.1): a skill mandava usar **`git add -p`** para preparar hunks. Sem
  terminal esse comando **sai com código 0 e não põe nada em stage** (reproduzido num repo de
  teste): o commit seguinte saía vazio ou errado, sem aviso nenhum. O caminho padrão agora é
  `git apply --cached` com o patch escrito em arquivo. O `git reset` do passo 6, única ação
  destrutiva da skill, passou a ser anunciado no plano antes da aprovação.
- **Nomes reais de projeto tinham vazado para o plugin publicado.** `git grep` em `origin/master`
  achava codinomes internos de projeto e dois hosts internos em 8 arquivos da `sw-infra-audit` —
  duas docstrings de código de produção (`lib/enrich.py`, `lib/stacks.py`), duas fixtures de teste
  e quatro arquivos de teste. Todos trocados por nomes fictícios (`loja-api`, `exemplo.test`).
  O **gate de segurança não pegava**, e esse era o buraco de verdade: ele procurava credencial,
  IP público e caminho do home, e nome próprio de projeto não é nenhum dos três. Agora o
  `scan_secrets.py` também recusa os nomes dos **contexts do docker** da máquina e os termos de um
  `.scan-denylist` opcional — as duas fontes fora do git, porque publicar a lista de nomes
  proibidos é publicar o que ela protege. A regra foi verificada contra o conteúdo real do commit
  anterior, que ela acusa.
- `sw-infra-audit` (v0.10.2): `detect_kind` deduzia o tipo do serviço por substring na referência
  inteira da imagem, tag incluída. Isso **salvava** um caso real (bundle em que a ferramenta só
  aparece na tag, `…/template-swarm-monitoring:prometheus-v2.44.0`) e **errava** outro: uma
  aplicação com tag `postgresql-latest` virava `banco`, entrava em `metrics.STATEFUL` e saía no
  relatório como ponto único de falha **com estado** — risco inventado, não rótulo feio. A tag
  agora só decide quando nomeia o produto no primeiro segmento e **nunca** decide um tipo com
  estado; bundle que esconda um serviço com estado continua com a saída de sempre, declarar
  `papel` no `[[alvo.componente]]`.
- `sw-infra-audit` (v0.10.1): três defeitos que só apareceram ao rodar a skill contra um cluster
  de verdade. **(1)** `configurar.py alvos --sugerir` estourava `KeyError: 'por_que'` — o impressor
  lia uma chave que o `discover.propose` nunca produziu, então o comando morria em qualquer cluster
  que tivesse um Prometheus. Ele é justamente o que o SKILL.md manda oferecer quando um componente
  está calado. Os três testes que o cobriam **fabricavam o candidato à mão**, com a chave inventada,
  e assim validavam a própria invenção; agora passam pelo `propose` real e uma trava de contrato
  quebra se impressor e produtor se separarem de novo. **(2)** A dimensão de higiene e a regra
  `SEC_IMAGE_UNPINNED` tinham definições **diferentes** de "imagem fixada": a regra recusa
  `tag == latest`, a dimensão só olhava o digest. Como o Swarm resolve `app:latest` para
  `app:latest@sha256:…` no deploy, o mesmo serviço contava dos dois lados — um relatório real saiu
  com "96% das imagens fixadas" ao lado de 31 achados de imagem não fixada, sobre os mesmos
  serviços. As duas passaram a usar `rules.imagem_fixada`. **(3)** `discover.propose` caía na
  primeira porta publicada quando a porta do catálogo não estava: propunha
  `http://host:80/metrics` para o Traefik (entrypoint HTTP, a métrica é a 8080) e `:15672` para o
  RabbitMQ (UI de administração, a métrica é a 15692 do plugin). Agora a porta é sempre a do
  catálogo, e `published` diz se **essa** porta está publicada.
- `sw-infra-audit` (v0.10.0): auditar um alvo **não-Swarm** quebrava a coleta. O Docker devolve
  `services` como aviso (`{"status": "n/a"}`) nesse caso, e dois laços iteravam nisso como se
  fosse lista — percorrendo as *chaves* do dicionário e estourando no primeiro `.get`. Dois
  testes cobrem o caminho.
- `sw-infra-audit` (v0.9.1): o SKILL.md mandava rodar **`alvos.py --sugerir`**, script que não
  existe — o correto é `configurar.py alvos --sugerir --context <ctx>`. E o
  `references/finding-rules.md` afirmava que achado `high` pinta a saúde de vermelho, o
  **oposto** da regra da skill ("saúde é operação, não higiene"). Os dois corrigidos; a mesma
  referência agora diz que cobre só a família `SEC_*` e que o registro real são as 21 regras de
  `lib/regras.py`. A doc da allowlist voltou a bater com o código, incluindo `(system, df)` e
  `(node, ps)`, que faltavam.
- `sw-code-review` (v0.1.3): o `references/checklist.md` ainda ensinava o fluxo antigo de
  resposta por texto (`s/n/arquivo/todos/parar`) em três exemplos e numa tabela, enquanto o
  SKILL.md chama isso de proibido — e exemplo é o que o modelo copia. Todos passaram a apontar
  para o menu do `AskUserQuestion`.
- `sw-auto-test` (v0.1.1): o sinal `runner_ausente` era emitido pelo `diagnose.py` e **não
  existia** no catálogo que a skill manda consultar. Entrou no catálogo, e um teste novo casa
  todo sinal emitido com o seu verbete. O achado "caminho crítico sem teste" era **impossível
  de registrar**: o validador recusava qualquer caminho fora do inventário, que só lista
  arquivos de teste. A dimensão `cobertura` passou a aceitar arquivo de produção, desde que ele
  exista no projeto. Também saiu a contradição entre "nunca pule a pergunta do tipo de teste" e
  "pule a pergunta quando…".
- `sw-study-buddy` (v0.2.0): o bloco de callout documentava a classe `callout__label`, que não
  existia no tema — o rótulo saía sem estilo. E a variante `.tip`, anunciada na referência,
  não tinha CSS. As duas corrigidas.
- `sw-pr-message` (v0.1.1): comentário no `lib/coleta.py` apontava para
  `referencias/calibracao-do-diff.md`, arquivo que não viaja com a skill.
- `sw-frontend-component-kit` (v0.3.2): os catálogos citados no piso anti-genérico são da
  `sw-frontend-mockup-preview`, e o caminho estava escrito como se fossem da própria skill.

### Alterado
- **Fronteira de disparo nas 14 skills.** Seis descrições não diziam quando **não** disparar, o
  que é o que o roteador lê. Entraram fronteiras explícitas em `sw-auto-test` (não é
  sw-skill-test nem sw-code-review), `sw-code-review` (não é dead-code-scan, auto-test nem
  pr-message), `sw-git-commit` (não é pr-message, nem push/amend/rebase; dentro da sw-plan
  espera o checkpoint), `sw-frontend-mockup-preview` (não é component-kit nem flow-diagram) e
  `sw-study-buddy` (não é leitura do código deste projeto nem diagrama). Gatilhos que faltavam
  também entraram: flakiness e lentidão na auto-test, "acha bugs nisso" e "security review" na
  code-review.
- `sw-study-buddy` (v0.2.0): publicado o subsistema de **retenção** que estava pronto e parado
  na máquina — repetição espaçada com intervalos 1/2/4/8/16/30, pontos fracos, prova por módulo,
  flashcards, glossário, mapa mental, streak e XP (`scripts/review.py`,
  `references/retention.md`), mais cinco tipos novos de ficha e os chips na barra lateral.
- A `sw-cluster-audit`, substituída pela `sw-infra-audit` e já retirada do marketplace, **ainda
  vencia o disparo** de "analisa meu cluster" na máquina, porque a frase estava literal só na
  descrição dela. Os gatilhos passaram para a `sw-infra-audit` e, portadas as seções de
  relatório que só ela tinha (nós, disco, redes, secrets, certificados e o roteamento do
  Traefik por aplicação), a cópia local foi **apagada** — o código segue recuperável no
  commit `fca83bf`.

### Adicionado
- `sw-infra-audit` (v0.10.0): o relatório ganhou **Cluster** e **Por aplicação**, as duas seções
  que só existiam na skill substituída. A coleta já trazia nós, disco, redes, secrets e
  certificados desde sempre — o v3 guardava e não desenhava. Agora a tabela comparativa dos nós
  volta (engine, plataforma, capacidade, tasks), as falhas recentes aparecem **agrupadas por
  código de saída** com a pista do que aquele código significa, e cada stack vira um bloco com
  os seus serviços e as rotas do ingress — que é como se responde "como o Traefik está roteando
  pro app X" sem ler serviço por serviço. Alvo que não tem esses fatos (um endpoint HTTP) não
  ganha seção vazia, e TLS sem certificado legível não vira tabela só com cabeçalho.
- `sw-frontend-mockup-preview` (v0.8.0): três referências novas, para o movimento e a estrutura
  deixarem de ser chutados no dia. **`references/animacoes.md`** (escala de duração, curvas
  prontas, padrões de micro-interação, movimento de dashboard, CSS × biblioteca e o que não
  fazer), **`references/esteticas-2025.md`** (perfis de tokens de seis referentes — bento,
  vidro intencional, neo-brutalism, dark-first, soft minimal e editorial — com o que evitar e
  qual exceção declarar no detector) e **`references/layouts-dashboard.md`** (shells, linha de
  KPI com hierarquia, grade de gráficos, tabela data-dense, filtros e densidade). As três estão
  ligadas no fluxo e no checklist da skill.
- `sw-frontend-component-kit` (v0.3.1): o bootstrap aponta para o catálogo de estéticas, e o
  combo Dashboard passa a **compor** seguindo os padrões de painel, em vez de entregar as peças
  soltas.

### Corrigido
- `sw-frontend-mockup-preview` (v0.8.0): a descrição ganhou os gatilhos **"refaz do zero",
  "redesenha a tela" e "algo completamente diferente"** — o teste de disparo mostrou que essas
  frases empatavam entre juízes, apesar de serem exatamente as que a skill usa no corpo para
  definir o modo "nova direção".
- `sw-frontend-component-kit` (v0.3.1): o piso anti-genérico passa a dizer que **texto sobre
  variante colorida sai de token** (`--on-accent`, `--on-error`), nunca de hex direto — foi por
  aí que o "zero hardcode" vazou num teste real (dois literais, no Button e no Badge).
- `sw-frontend-mockup-preview` / `sw-frontend-component-kit`: a referência de dashboard prometia
  que o detector acusa "KPIs todos iguais"; ele só acusa **exatamente três** colunas iguais, e
  com 4 ou 5 fica calado. O texto agora diz isso. Itens de lista desencaixados nos dois
  `SKILL.md` voltaram para a indentação certa.

### Adicionado
- `sw-plan` (v0.6.0): **`scripts/plan_check.py`**, o lint determinístico do plano. Acusa task sem
  arquivos, step que mexe em código sem mostrar o código, placeholder (`TODO`, "adicionar
  validação", "igual à Task N"), checkbox torto, dependência para task que não existe e
  **arquivo de "Alterar" que não existe no projeto** — o typo de caminho que só apareceria no
  meio da execução. 17 testes de biblioteca padrão.
- `sw-plan` (v0.6.0): **ordem por risco (spikes-first)** — a primeira task passa a ser a que
  pode derrubar o plano, não a mais fácil; **retomada de execução** a partir da primeira task
  não marcada, com o log `## Ajustes durante a execução`; **menu de recuperação** quando um step
  falha (ajustar o plano, refazer o batch ou parar), com parada obrigatória na terceira falha
  seguida; **contratos acumulados** passados ao subagente, para a task seguinte encaixar na
  anterior; e **estimativa** (tasks, batches e porte) no resumo de aprovação.
- `sw-brainstorming` (v0.7.0): o spec ganhou a tabela de **Suposições** (`Suposição · Risco se
  for falsa · Como validar`), que é o que a `sw-plan` usa para ordenar as tasks pelo risco, e a
  seção **Rollout e reversibilidade** (feature flag, etapas, plano de volta, dados existentes),
  proporcional ao risco.
- `sw-brainstorming` (v0.7.0): **retomada com "onde paramos"** — ao continuar um dossiê, a skill
  resume o que já foi decidido, o que ficou em aberto e o próximo passo, em vez de mandar o
  usuário lembrar; e o **caminho oficial para mexer num spec já aprovado** (voltar o estado,
  discutir só o que mudou, registrar em `## Revisões do spec`).
- `sw-brainstorming` (v0.7.0): o **índice do dossiê mostra o andamento** (`plano 3/7`) lendo os
  checkboxes do `plan.md` — uma task só conta como feita quando todos os steps dela estão
  marcados.

### Corrigido
- `sw-plan` (v0.6.0): o template de task mandava **commitar dentro da task**, enquanto a regra
  dos checkpoints diz "nunca commite sem o sim". No modo Subagent isso fazia o subagente
  commitar sozinho. O step de commit saiu: commit é no checkpoint, com aprovação.
- `sw-plan` (v0.6.0): o `plan-document-reviewer-prompt.md` existia e **nenhum passo o usava**.
  Agora o revisor do plano é oferecido depois do self-review e antes do gate de aprovação.
- `sw-plan` (v0.6.0): a skill nunca mencionava as **fitness functions** que o spec da
  `sw-brainstorming` manda escrever. O cabeçalho do plano passa a ter a tabela
  `Restrição · Como o plano checa`, e o self-review cobra a que ficou sem verificação.
- `sw-plan` (v0.6.0): o cabeçalho obrigatório não tinha o **link do spec** que o próprio texto
  exigia; **Cancelar** no gate não tinha efeito definido (agora: não executa nada, o plano fica
  no dossiê e o estado não avança); o caminho do `dossie.py` era fixo em `~/.claude/skills/` e
  quebrava com a skill instalada como plugin (agora é procurado também no cache de plugins).
- `sw-plan` (v0.6.0): metade do arquivo estava em inglês herdado do original (inclusive "our
  codebase and questionable taste") e a Execution Handoff em português sem acento. Tudo em
  português, e o resíduo `superpowers:*` saiu.
- `sw-brainstorming` (v0.7.0): a skill citava a "Task tool", nome que não existe mais nesta
  versão do Claude Code — a ferramenta é a `Agent`.

### Corrigido
- `sw-brainstorming` (v0.6.2): **`--raiz` depois do subcomando não funcionava.**
  `dossie.py novo --titulo X --raiz Y` morria em `unrecognized arguments` — justamente a ordem
  que o próprio `SKILL.md` sugere no fallback. Agora vale nas duas posições, e o valor passado
  antes do subcomando não é mais sobrescrito pelo padrão.
- `sw-brainstorming` (v0.6.2): slug sem o prefixo de data dava erro seco; agora o script
  **sugere o dossiê certo** (`você quis dizer: 2026-09-25-...?`). Espaços sobrando no fim das
  linhas da listagem e do código também saíram.
- `sw-brainstorming` (v0.6.2): o prompt do revisor misturava inglês e português na mesma frase,
  a variante "spec" estava inteira em inglês (inclusive o formato da resposta) e apontava o
  caminho **de fallback** (`~/.claude/projects/...`) como se fosse o padrão, que é `docs/specs/`.
  O arquivo foi reescrito em português, com o caminho certo.

### Alterado
- `sw-brainstorming` (v0.6.2): o revisor do spec passa a cobrar o que o auto-review já cobrava e
  ele ignorava: **não-objetivos, restrição de simplicidade, appetite e corte MVP, decisões com
  alternativas descartadas e fitness functions que dê para checar**.
- `sw-brainstorming` (v0.6.2): o diagrama do fluxo ganhou o passo 0 (ver dossiês existentes e
  continuar um em vez de abrir outro), que só existia no checklist; o caminho trivial passa a
  dizer que **não é caso de disparar a skill**, alinhando com o frontmatter; a transição para a
  `sw-plan` ganhou saída quando ela não está instalada; e ficou escrito **quem marca cada
  estado** do dossiê (esta skill marca `aprovado`; `em-execucao` e `concluido` são da `sw-plan`).

### Adicionado
- `sw-brainstorming` (v0.6.2): `tests/` com 14 testes de biblioteca padrão para o `dossie.py`
  (slug com acento e pontuação, frontmatter, dossiê duplicado recusado, estado gravado e
  validado, sugestão de slug, índice regenerado entre os marcadores sem apagar o resto do
  README).

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
