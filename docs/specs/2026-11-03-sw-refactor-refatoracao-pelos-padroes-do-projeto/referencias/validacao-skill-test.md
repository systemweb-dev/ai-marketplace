# Validação pela sw-skill-test

Executada em 2026-11-03. Fixture copiado para diretórios temporários com `git init`, sem o
`GABARITO.md`. Respostas do roteiro da Task 9. Duas rodadas com a skill (a 2ª depois das correções)
e uma de baseline (mesmo pedido, sem a skill).

## Comportamento

| Item | Esperado | Rodada 1 | Rodada 2 | Baseline |
|---|---|---|---|---|
| D1 payments | apontado; pulado | ✓ | ✓ | não mexeu, sem perguntar |
| D2 / R1 shipping | falha e restauração só da etapa | ✓ igual ao original | ✓ igual ao original | não mexeu |
| D3 camelCase | aplicado | ✓ | ✓ | não mexeu |
| D4 fábrica sem uso real | apontado | ✗ | ✓ | não apontou |
| D5 aninhamento | aplicado | ✓ | ✓ | ✓ |
| D6 / P1 conflito PHP 6 × 5 | perguntado | ✓ | ✓ | ✗ decidiu sozinho (Request) |
| D7 get_taxe | aplicado | ✓ | ✓ | ✓ |
| C1 / P2 contrato | perguntado, não aplicado | ✓ | ✓ | deixou, sem perguntar |
| A1 armadilha | 0 edições | ✓ | ✓ | ✓ |
| P3 / P4 | perguntas presentes | ✓ | ✓ | — |
| Testes finais | verdes | ✓ | ✓ | ✓ |

Checagens estáticas: `SKILL.md` sem script (grep vazio) e ponto de restauração antes da edição.

## Disparo

14 frases (7 devem disparar, 7 pegadinhas: review de diff, código morto, migração de versão,
formatter, escrever testes, renome pontual, monólito → microserviços). Dois juízes com só nome e
descrição: 14/14 nos dois.

## O que a skill agrega sobre o baseline

O baseline é competente: respeita a armadilha, não quebra teste e evita o contrato. A skill agrega
o que ele não faz: pergunta no conflito em vez de escolher sozinho (o baseline escolheu o lado
oposto ao do dono e criou 6 classes), separa e pergunta o que muda contrato, prova cada etapa com
teste e restaura só a etapa que falha, e alcança desvios que o baseline deixou de lado por não ter
como provar (D1 a D3).

## Correções feitas a partir da validação

- Recontagem abaixo de 80% também na reference (estava 70%).
- Arquivo que só captura ou repassa não conta na unidade; arquivo de teste também não, exceto em
  "onde ficam os testes".
- Dimensão nova no grupo e: abstração sem uso real (corrigiu o D4).
- "Cobre" = um teste executa a função mudada; importar não basta.
- Arquivos criados pela etapa listados em `"$PONTO.criados"` para a restauração.
- Auxiliar que a própria etapa deixou sem uso é removido nela; código já sem uso fica para a
  `sw-dead-code-scan`.
- Cache de teste (`__pycache__/`) ignorado no `git status` e apagado ao fim da etapa.
- Etapa separada por cobertura (com teste × sem teste), para a falha de um não desfazer o outro.

## Recomendações não aplicadas (ficam para uma versão futura)

- Regra para dimensões que se sobrepõem entre grupos (ex.: "quem chama quem" e validação PHP).
- Custo da recontagem: uma dimensão por subagente somou 4 subagentes num projeto de 37 arquivos.
- Arquivo com duas variantes (ex.: `api.py`): os subagentes o colocaram em variantes diferentes.

## Limitações

Fixture sintético e pequeno; o juiz de disparo é proxy do roteador; a skill rodou por subagente,
sem usuário real. Vale uma rodada num projeto real antes de recomendar a outras pessoas.
