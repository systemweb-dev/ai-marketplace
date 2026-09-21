---
titulo: Mockup com leitura do pedido, variações por eixo e detector anti-slop
slug: 2026-09-21-mockup-com-leitura-do-pedido-variacoes-por-eixo-e-detector-anti-slop
criado: 2026-09-21
estado: concluido
---

# Mockup com leitura do pedido, variações por eixo e detector anti-slop

> Dossiê deste trabalho. `spec.md` é a fonte da verdade do design; `referencias/` guarda o
> material de apoio.

## Objetivo & outcome

A `sw-frontend-mockup-preview` gera variações e as serve com live-reload, mas decide a direção
às cegas, entrega variações parecidas entre si e não tem piso de qualidade verificável. O dono
quer potencializá-la com duas referências públicas e **absorver nela o papel do
`sw-design-studio`**, que sai do marketplace ("o mockup já auxilia").

Outcome: um pedido de mockup produz, sem entrevista longa, variações que diferem de verdade,
passam por um detector determinístico de "tells" de IA, e podem ser ajustadas ao vivo no
navegador sem gerar de novo.

## Referências (licença permissiva, adaptadas e creditadas — nunca copiadas)

| Projeto | Licença | O que inspira |
|---|---|---|
| Impeccable (pbakaus/impeccable) | Apache-2.0 | piso de qualidade (verificar × recusar), modos por tipo de tela, variações por eixo com trava de identidade e teste do olhar semicerrado, knobs por variação, vocabulário de refino, verificação em rodada única |
| Taste Skill (Leonxlnx/taste-skill) | MIT | leitura do pedido em uma linha, uma pergunta só quando diverge, catálogo de tells (dados "Jane Doe", números perfeitos, verbos de enchimento, tela de produto falsa em `div`, rótulos numerados, travessão) |

Texto próprio, em português. O crédito vai no README, no CHANGELOG e no cabeçalho dos arquivos
de referência que adaptam as ideias.

## Decisões do dono (2026-09-21)

1. **Remover o `sw-design-studio`** do marketplace e da máquina. Antes, o glossário
   `tecnicas-de-design.md` dele vai para o mockup. As skills que o citam (`sw-brainstorming`,
   `sw-frontend-component-kit`, o próprio mockup) são ajustadas.
2. **Trazer as quatro peças:** leitura do pedido + variações por eixo; detector anti-slop + piso
   de qualidade; knobs ao vivo no canvas; vocabulário de refino.
3. **Travessão proibido no texto de interface** (botão, título, rótulo, legenda, navegação); em
   texto corrido longo ele pode ficar. O detector acusa.
4. **Modo didático opcional** — o glossário vem junto, e a explicação só aparece se pedida.
5. Depois do mockup, **revisar a `sw-frontend-component-kit`** e dar a ela variações para o
   usuário entender (trabalho separado, depois deste).

## O que muda na skill

### 1. Leitura do pedido (substitui a entrevista do design-studio)

Antes de gerar, uma linha: *"Lendo como: \<tipo de tela> para \<público>, em linguagem
\<vibe>, no modo \<convencer | operar | ler | experimentar>."* O **modo** vem da tela pedida,
não do produto (a landing de uma ferramenta é *convencer*; o painel dela é *operar*).

Uma pergunta, uma só, e só quando a leitura diverge de verdade. Inferível → declara e segue.

### 2. Variações que diferem de verdade

- **Trava de identidade:** uma frase com o que está na tela hoje (cor de superfície e acento
  com valores reais, par de fontes carregado, topologia, tratamento de superfície, tom da cópia).
- **Dois modos:** *mesma identidade* (padrão, ~90%) varia a expressão dentro da trava; *nova
  direção* só quando o usuário pede ("refaz do zero", "algo completamente diferente").
- **Cada variação num eixo primário diferente:** hierarquia · topologia do layout · sistema
  tipográfico · estratégia de cor · densidade · decomposição estrutural.
- **Teste do olhar semicerrado** antes de entregar: nenhuma variação vaza da trava (no modo
  padrão), e as três não rimam entre si.

### 3. Piso de qualidade e detector

- `references/piso-e-recusas.md`: o que **verificar** no resultado (contraste, profundidade,
  espaçamento, medida de linha, estados, superfícies do navegador, cópia) e o que **recusar**
  por ser padrão de categoria (cards iguais como estrutura, template de número-herói, rótulo
  numerado de seção, texto em gradiente, borda colorida lateral, emoji como ícone, dados "Jane
  Doe", tela de produto falsa em `div`, travessão na interface...).
- `scripts/detectar.py`: varredura **determinística** do HTML do mockup (sem LLM), com regras
  nomeadas, linha, e dica de correção. Saída 0 = limpo, 2 = achados. Desligável por comentário
  no HTML quando o brief pede a exceção.
- **Verificação em rodada única:** constrói inteiro, confere desktop e mobile juntos, conserta
  tudo de uma vez, no máximo mais uma conferência. Nada de ciclo aberto de autoajuste.

### 4. Knobs ao vivo

Cada variação declara de 0 a 4 knobs em `data-knobs` (JSON): `range` (slider → variável CSS
`--k-<id>`), `steps` (segmentado → atributo `data-k-<id>`) e `toggle`. O harness desenha os
controles da variação ativa na barra, sem regenerar. Orçamento por peso visual: folha (botão,
ícone) 0; composição pequena 0–1; média ~2; grande 2–4.

### 5. Vocabulário de refino

Depois do primeiro render, o próximo passo é um menu: **mais ousado · mais calmo · enxugar ·
polir · tipografia · cor · layout · movimento · adaptar**. Cada escolha gera variações na
dimensão dela, cada uma variando uma faceta diferente (ex.: "mais ousado" = escala, saturação,
estrutura).

### 6. Modo didático

Opcional. Com ele ligado, cada decisão vem com uma dica curta nomeando a técnica, tirada de
`references/tecnicas-de-design.md`.

## Restrições verificáveis

1. `detectar.py` acusa cada regra do catálogo num HTML de exemplo e não acusa nada num HTML
   limpo — um teste por regra, com mutação.
2. `detectar.py` não importa rede nem subprocesso, e roda só com a biblioteca padrão.
3. O harness continua funcionando sem nenhuma variação declarando knobs (compatível com
   mockups antigos).
4. Nenhuma skill do marketplace cita `sw-design-studio` depois da remoção (fora o CHANGELOG,
   que é história).

## Não-objetivos

Hook automático que roda o detector a cada edição · ferramentas de navegador ao vivo com
seleção de elemento (o "live mode" do Impeccable) · catálogo de estéticas fixas (soft,
brutalist, minimalist...) · geração de imagem.

## Ordem de execução

1. Remoção do design-studio (glossário antes, referências depois).
2. Detector + piso de qualidade (código com teste).
3. Knobs no harness.
4. SKILL.md: leitura do pedido, eixos, refino, didático, verificação em rodada única.
5. Publicação: mockup (minor), brainstorming e component-kit (patch), CHANGELOG.
