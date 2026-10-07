# Spike — a prosa de produto se sustenta?

**Projeto A** (com fonte textual rica): CRM single-tenant de um nicho técnico, stack única,
um `CLAUDE.md` de 11 KB que declara propósito, público e invariantes.
**Projeto B** (só código): monorepo por justaposição — três aplicações lado a lado (painel
administrativo, API, site público), duas stacks, **sem documentação útil**: o README mais
longo tem 2 KB e é boilerplate de framework; o mais curto, 26 bytes.
**Data:** 2026-10-07

Os dois são projetos reais. Nomes de projeto, de cliente e caminhos de máquina ficam fora
deste arquivo de propósito: o repositório é público.

## Parte 1 do projeto A

Validada **fora deste spike**, pelo mockup que o dono aprovou em 07/10. O documento inteiro
— abertura narrativa, retrato, o que o projeto diz de si — foi escrito a partir do inventário
desse projeto e de cinco arquivos. O dono leu, pediu **mais** detalhe duas vezes e aprovou a
forma. A prosa com fonte textual rica não está em dúvida.

**Fonte citada:** `CLAUDE.md` — uma frase que declara, de uma vez, o modelo de instalação, o
setor e a ordem de grandeza de usuários.
**Arquivos lidos além do inventário:** 5.

## Parte 1 do projeto B

> Três aplicações moram lado a lado neste repositório, sem nada que as amarre: um painel
> administrativo em Vue (1.277 arquivos), uma API em PHP (409) e um site público (233).
> Cada uma tem o seu manifesto; nenhuma importa a outra. O que as liga é a API, que as duas
> pontas consomem por HTTP.
>
> O sistema põe **marcas e agências** em contato com **criadores de conteúdo** para executar
> **campanhas**. Isso não está escrito em lugar nenhum: sai dos nomes. As rotas do painel são
> `v1/campaign`, `v1/creator`, `v1/brand`, `v1/agency`; a campanha tem `status_approval` e
> `status_workflow` separados, tem `date_from` e `date_to`, e tem rotas próprias para
> `campaign-payment/pay` e `campaign-commission/pay` — logo, o dinheiro corre em duas pernas,
> o que se paga ao criador e o que se retém como comissão.
>
> Um detalhe diz mais sobre o negócio do que qualquer outro: o sistema trata **criador menor
> de idade**. Há `birth_date`, um campo `guardian_name`, um `guardianConfirmedAt`, uma classe
> com `Minor` no nome, e dois jobs de e-mail dedicados — um que **pede** o consentimento do
> responsável e um que registra a **recusa** dele. São 68 ocorrências de `guardian` no código
> da API. Alguém desenhou um fluxo de consentimento, e ele tem estado próprio.
>
> O que o sistema toca por fora, pelos nomes das variáveis de ambiente: AWS (credencial e
> região), um provedor de e-mail transacional, a API de uma rede social — há uma rota
> `creator/sync-instagram` — e um webhook de chat para log. A autenticação é JWT, com chaves
> **separadas** para administrador e para criador: são dois públicos, não um com dois papéis.

**Arquivos lidos além do inventário:** 5 — o arquivo de rotas do painel (o mais co-mudado do
projeto, 38 vezes com o middleware), o modelo de campanha, um dos jobs de consentimento, e
duas buscas por termo no diretório da API.
**O que não deu para afirmar, e por quê:**
- **quem opera o painel** — administrador da casa? da agência? O código tem um só perfil de
  administrador, mas isso não diz quem senta na cadeira.
- **se o site público é vitrine ou produto** — tem 233 arquivos e stack própria; não dá para
  distinguir landing page de aplicação sem abrir as telas.
- **o que o nome do produto significa no vocabulário do negócio** — ele aparece em nome de
  variável de ambiente e de chave JWT, mas nunca como entidade no código. Pode ser só a marca,
  ou um conceito que não foi implementado.
- **quais das três aplicações estão em produção hoje** — nenhuma das três declara.

## Veredito

- O dono achou a do projeto A melhor que nada? **sim** — aprovou e pediu mais.
- E a do projeto B? **sim** — o parágrafo do consentimento de menor é o tipo de frase que
  economiza uma reunião, e saiu só de código.
- **Decisão: a parte 1 fica como desenhada.** As tasks 9 a 11 não encolhem.

## O que o spike mudou no desenho

A regra atual do `SKILL.md` diz, com todas as letras: *"propósito e público só com fonte
textual. Se não houver README, ADR, mensagem de commit ou texto de tela dizendo para que o
sistema serve, não afirme."* Ela nasceu para impedir prosa plausível e vazia, e isso continua
certo — mas o projeto B mostra que ela é **estrita demais**, e que custa caro.

Dizer "este sistema conecta marcas a criadores de conteúdo" não é adivinhação quando quatro
fontes independentes convergem: rota, coluna de tabela, job e middleware. Recusar essa frase
por falta de README joga fora a informação mais útil do documento.

**Regra nova, para as tasks 9 a 11:** propósito pode sair como `deducao` **quando houver
evidência convergente de pelo menos três fontes de natureza diferente** (rota, nome de coluna,
job, middleware, nome de arquivo), e as evidências forem **todas citadas**. Com uma fonte só,
ou com fontes do mesmo tipo, continua `lacuna`. O que sai de texto escrito por humano
continua `declarado`, e vence a dedução quando os dois existem e discordam — mostrando os dois.
