# Piso de qualidade e recusas

Leia **depois** de decidir a direção e **antes** de escrever o markup das variações. O que está
aqui não escolhe a direção — garante o piso. Com o piso verde, gaste o mockup na direção
escolhida; na dúvida entre "refinado" e "comprometido", comprometa.

> Adaptado, com texto próprio, de duas referências públicas: o *craft floor* do
> [Impeccable](https://github.com/pbakaus/impeccable) (Apache-2.0) e o catálogo de "AI tells"
> da [Taste Skill](https://github.com/Leonxlnx/taste-skill) (MIT).

**O brief vence.** Uma estética, fonte ou paleta pedida por extenso (ou já no design system do
projeto) vale mais que qualquer recusa daqui. Recusa é para quando o eixo está livre e o
padrão apareceu sozinho — reconhecer isso é reescrever o elemento, não suavizá-lo.

## Verificar (no resultado construído, não na intenção)

Tudo numa rodada só: desktop e mobile juntos, conserta tudo de uma vez, no máximo mais uma
conferência. Ciclo aberto de autoajuste gasta o tempo do usuário fazendo pior o que o olho
dele faz melhor.

- **Contraste:** texto de corpo e placeholder ≥ 4,5:1; texto grande ≥ 3:1. Sobre superfície
  colorida, o texto secundário puxa o tom daquela cor — nunca cinza neutro.
- **Profundidade:** sombra tem deslocamento e desfoque. Halo colorido sem deslocamento é
  enfeite.
- **Espaçamento:** grupo apertado, separação generosa, mais espaço acima do título que abaixo.
- **Tipografia:** medida do corpo entre 65 e 75 caracteres; escala e peso com degraus óbvios;
  a cópia real em todo breakpoint — o que estourar, conserte.
- **Movimento:** um momento autoral, não efeitos espalhados nem a mesma entrada em toda seção.
  Saída exponencial a partir de um estado já visível. Guarda `prefers-reduced-motion` sempre.
- **Estados:** hover, desabilitado, carregando, erro, vazio. Conteúdo real, controle que
  funciona, foco de teclado visível.
- **Superfícies do navegador:** seleção de texto, cursor de texto, barra de rolagem, anel de
  foco, sublinhado e numerais de tabela saem com o padrão do navegador, que não pertence a
  design nenhum. Tema-os pela paleta: é o sinal mais barato de que a tela foi construída, e o
  que modelo mais esquece.
- **Cópia:** a língua do produto. Botão diz a ação ("Salvar alterações", não "Enviar"); erro
  diz o problema e a saída.
- **Cobertura:** tudo que o pedido citou está lá, e se acha em segundos.

## Recusar (padrões de categoria)

Marcados com `[detector]` quando `scripts/detectar.py` acusa sozinho — no CSS, nos `style=""`,
nas classes utilitárias (Tailwind) e nos atributos de texto (`placeholder`, `aria-label`,
`title`, `alt`, `value` de botão). Os outros dependem do seu olho. O detector é uma rede, não
um juiz: pega o padrão escrito do jeito comum, e nenhum detector estático pega todas as grafias.

**Estrutura da tela**
- Cards do mesmo tamanho com ícone + título + texto como estrutura da página. Card é o
  recipiente preguiçoso; card dentro de card está sempre errado.
- Três colunas iguais como linha de recursos `[detector: aviso]` (inclui `repeat(3, 1fr)`,
  `repeat(3, minmax(0, 1fr))` e a classe `grid-cols-3`). Prefira zigue-zague em duas
  colunas, grade assimétrica ou rolagem horizontal — quando o conteúdo é dado tabular, três
  colunas iguais podem ser a resposta certa.
- O template de número-herói: número grande, rótulo pequeno, estatísticas de apoio, acento.
- Rótulo numerado de seção (`01 / Recursos`, `002 · Serviços`, `03`) `[detector]`. Se a
  sequência não informa nada ao leitor, o título fala sozinho.
- Rótulo acima do título ("eyebrow") só para enfeitar. Apague e deixe o título falar.
- Modal para tarefa que não precisa nem de interrupção nem de foco protegido.
- Tela de produto falsa feita de `div` (lista de tarefas, terminal, painel desenhados com
  retângulo). Use imagem real, componente real, ou nada.

**Superfície**
- Texto em gradiente `[detector]`. Ênfase vem de peso ou tamanho.
- Preto puro `[detector]` — `#000` achata a profundidade. Use um quase-preto tingido. (Pega
  `#000`, `#000000`, `#000f`, `black`, `rgb(0 0 0)`, `rgba(0,0,0,1)`, `hsl(0 0% 0%)`, token
  `--x: #000` e a classe `bg-black`; preto translúcido em sombra continua permitido.)
- Borda colorida à esquerda ou direita acima de 1px em card, item de lista, aviso
  `[detector]` (px, rem, ordem livre, `border-width` de quatro valores, `border-l-4`; borda
  transparente não conta).
- Sombra dura sem desfoque (`4px 4px 0`) fora de um mundo que escolheu ser neobrutalista
  `[detector: aviso]`.
- Halo colorido sem deslocamento (`0 0 24px #7c3aed`) como brilho decorativo
  `[detector: aviso]`. Sombra ambiente neutra e anel de foco (`0 0 0 3px`) não contam.
- Vidro e desfoque como decoração, e não como efeito específico.
- Easing elástico ou com "quique" `[detector]` — soa datado.
- Cursor personalizado `[detector]` — hostil à acessibilidade e ao desempenho.
- Monoespaçada como fantasia de "técnico", e não para código, dado ou medida.
- Emoji ou símbolo unicode no lugar de ícone `[detector]`. Ícone vem de uma biblioteca real ou
  de SVG autoral, com traço e peso consistentes.
- Bolinha de status colorida em todo item, quando não indica estado real.
- "Pill soup": toda etiqueta, filtro e status virando pílula cinza igual.
- Toggle no estilo iOS padrão, sem nenhuma adaptação à direção.
- A mesma sombra suave em tudo, e o mesmo raio em tudo — profundidade e forma sem hierarquia.
- Claro ou escuro escolhido pela categoria do produto. Escolha pela cena de uso: quem, onde,
  sob que luz.

**Texto e dados** (o efeito "Jane Doe")
- Nome genérico — `John Doe`, `Jane Doe`, `Fulano`, `Acme`, `Lorem ipsum`, `@example.com`,
  `@exemplo.com.br`, `(11) 99999-9999`, `000.000.000-00` `[detector]`, inclusive em
  `placeholder` e `value` de formulário, que é onde mais aparece. Invente nomes críveis, do
  lugar e do setor.
- Número perfeito demais — `99,99%`, `1234567` `[detector: aviso]`. Dado real é bagunçado:
  `47,2%`, `R$ 1.847,30`.
- Verbo de enchimento — *revolucione*, *eleve*, *sem esforço*, *próxima geração*, *seamless*
  `[detector: aviso]`. Verbo concreto: o que a pessoa faz.
- **Travessão (— ou –) no texto de interface** `[detector]`: botão, título, rótulo, link,
  item de navegação, cabeçalho de tabela, legenda, pílula, e os atributos `placeholder`,
  `aria-label` e `title`. Troque por ponto, vírgula, dois-pontos ou quebra de linha. Em
  parágrafo de texto corrido ele pode ficar — em português é pontuação legítima —, e a
  meia-risca de intervalo (`08h–18h`, `R$ 50–80`) está certa.
- Rótulo de etapa genérico (`Etapa 1 / Etapa 2 / Etapa 3`). O conteúdo da etapa é o rótulo.

## Quando o brief pede a exceção

Declare no próprio HTML, com a justificativa depois da lista, entre parênteses. A exceção vale
para o arquivo inteiro, e os achados suprimidos continuam listados, com linha, sob
**IGNORADAS** — nunca somem:

```html
<!-- detector: ignorar sombra-dura, tres-colunas-iguais (mundo neobrutalista; tabela de preços) -->
```

Só para exceção que o pedido justifica (um mundo neobrutalista pede sombra dura; uma tabela de
preços em três planos pede três colunas). Ignorar para o detector ficar verde é o mesmo que
não rodar.
