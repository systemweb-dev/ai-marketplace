# A demo que ensina

Leia **antes de gerar a página de demo** (Fase 5). A demo não é uma vitrine muda: quem abre
precisa sair sabendo **qual variante usar, quando, e como fica em uso de verdade**, sem abrir o
código. A referência visual pronta está em [`assets/demo-estudio.html`](../assets/demo-estudio.html)
(direção "Estúdio"): abra no navegador, e **porte** a estrutura para a stack do projeto com os
tokens do projeto e os componentes reais do kit. Não copie o HTML como está.

## A tela de cada componente (sempre nesta ordem)

1. **Lista lateral** dos componentes do kit, agrupados pelo combo, com o número de variantes ao
   lado. Componente ainda não gerado aparece desabilitado (mostra o que falta, sem mentir).
2. **Cabeçalho:** o nome e **uma frase** do que o componente faz e do que muda entre as
   variantes. Nada de parágrafo.
3. **Barra de controles dentro do conteúdo**, acima do palco (não num painel à parte): um
   controle segmentado por prop que muda a aparência (variante, tamanho, estado) e um campo para
   o texto principal. Só props reais do componente, com os nomes que o código usa.
4. **Palco de estúdio:** fundo escuro com luz no centro, a peça viva no meio, e uma legenda
   discreta embaixo com o estado atual (`primaria · md · padrao`). A peça é o componente real,
   com os handlers reais: clicar, focar e digitar funcionam.
5. **Todos os tipos:** todas as formas do componente **ao mesmo tempo**, sem depender dos
   controles. É onde se enxerga a consistência do kit. Veja o catálogo abaixo.
6. **Quando usar cada variante:** para cada variante, uma amostra pequena, **quando usar** (uma
   frase concreta, com exemplos de ação) e **Não use** (o erro comum, com a consequência).
7. **Exemplos em contexto:** de **3 a 5** usos reais do componente, cada um num cartão com
   título, **o porquê daquele arranjo** em uma frase, e o componente montado junto com o que o
   cerca (o rodapé do formulário, a linha da tabela, o diálogo). Dados críveis do domínio do
   projeto, nunca "Lorem" nem "John Doe".

**Sem código na página.** Nada de bloco de código, "copiar" ou snippet: o código e os exemplos
de uso moram no **docblock do próprio componente** (Fase 4). A demo mostra; o docblock ensina a
escrever.

**Tema claro e escuro** funcionando na página inteira, com os tokens. **Responsiva:** abaixo de
~860px a lista vira faixa horizontal e as tabelas de "Todos os tipos" rolam de lado.

## Catálogo: o que entra em "Todos os tipos" e nos "Exemplos em contexto"

Adapte ao que o componente gerado realmente tem: só mostre variante, tamanho e estado que
existem no código. Quando o componente tem variantes **e** tamanhos, use a tabela
**variantes × (tamanhos + estados)**; as formas extras vão em cartões embaixo dela.

| Componente | Todos os tipos | Exemplos em contexto |
|---|---|---|
| **Button** | variantes × pequeno/médio/grande/desabilitado/carregando; com ícone, só ícone (com nome acessível), largura total | rodapé de formulário, confirmação que destrói, ações numa linha de tabela, enquanto salva, barra de ferramentas |
| **Input** | texto, e-mail, senha (mostrar/ocultar), valor com prefixo, busca com ícone, com contador; estados padrão/foco/erro/desabilitado | formulário de cadastro, busca com botão, erro ao salvar (aviso no topo + erro no campo), bloqueado por permissão |
| **Card** | só conteúdo, com mídia, com ações, clicável inteiro, selecionado, carregando (skeleton) | lista de itens, card de resumo num painel, escolha entre planos |
| **Badge** | cada tom semântico (neutro, sucesso, atenção, erro, info) × sólido/suave; com ponto; numérico | status numa tabela, contador num menu, rótulo de novidade |
| **Avatar** | tamanhos; com foto, com iniciais, sem nada (ícone); com status; grupo empilhado com "+N" | autor de comentário, responsável numa linha, quem está online |
| **Typography** | a escala inteira (display → legenda) com peso e altura de linha; link; texto secundário | título de página com subtítulo, bloco de texto corrido, legenda de gráfico |
| **Select** | fechado, aberto, com busca, múltiplo, com grupo; estados | filtro de lista, campo de formulário, troca de ordenação |
| **Checkbox / Radio / Switch** | marcado, desmarcado, indeterminado (checkbox), desabilitado, com descrição | aceite de termos, grupo de preferências, liga/desliga que salva na hora (switch) |
| **Textarea** | vazio, preenchido, com contador, redimensionável, erro | comentário, observação de entrega |
| **DatePicker / DateRangePicker** | fechado, calendário aberto, intervalo, datas bloqueadas, erro | filtro de período, agendamento |
| **FileUpload** | vazio, arrastando, enviando com progresso, concluído, erro de tipo/tamanho | anexo em formulário, troca de foto |
| **Modal / Drawer** | tamanhos; com rolagem interna; de confirmação; de formulário | confirmar exclusão, editar item sem sair da lista, detalhes laterais |
| **Toast** | cada tom; com ação ("Desfazer"); empilhados | salvou, desfazer exclusão, falha de rede com "Tentar de novo" |
| **Alert** | cada tom; com título; com ação; dispensável | aviso no topo de formulário, manutenção programada |
| **Tooltip / Popover** | posições; com atalho de teclado; popover com conteúdo rico | explicar ícone, detalhe de um número |
| **Spinner / Skeleton / ProgressBar** | tamanhos; skeleton de texto, card e tabela; progresso determinado e indeterminado | carregando lista, enviando arquivo |
| **EmptyState** | primeira vez, busca sem resultado, erro, sem permissão | lista vazia com a primeira ação, busca que não achou |
| **Tabs** | sublinhado, segmentado; com contador; com ícone; desabilitada | seções de um detalhe, filtro rápido de lista |
| **Breadcrumb / Pagination** | curto, longo com recorte; página no meio, primeira, última | navegação de detalhe, lista paginada |
| **DropdownMenu** | itens simples, com ícone, com atalho, com separador, item perigoso | menu de ações de uma linha, menu do usuário |
| **Navbar / Sidebar** | expandida, recolhida, item ativo, com contador | layout do app, navegação no celular |
| **Table** | densidades; ordenável; com seleção; linha expandida; vazia; carregando | lista de pedidos com ações, tabela com filtro e paginação |
| **List** | simples, com ícone, com ação, com seleção | configurações, notificações |
| **StatCard / KPI** | com variação positiva e negativa, sem comparação, carregando | topo de painel, comparação de período |
| **Formulários de Auth** | login, cadastro, recuperar senha; estados de erro e envio | fluxo completo com mensagens reais |

Para componentes de **Marketing** (Hero, PricingCard, FAQ...), "Todos os tipos" são os arranjos
(com imagem, centralizado, dividido) e os exemplos são seções de página montadas com conteúdo do
produto.

## O que torna a demo boa (e não genérica)

- Cada frase de "quando usar" e "Não use" é **específica do componente** e fala da consequência
  para quem usa. "Use para ações importantes" não ensina nada; "Para a ação que conclui o que a
  pessoa veio fazer: salvar, enviar o pedido" ensina.
- Os exemplos em contexto usam o **vocabulário do produto** (os nomes, os dados, os verbos dele).
- A demo segue o mesmo piso de qualidade dos componentes: contraste, foco visível, estados de
  verdade, `prefers-reduced-motion`.
