# Catálogo de regras do diagnóstico

Ids estáveis: é por eles que um achado do agente se liga a um fato do script.

| Id | O que é | Dimensão | Confiança |
|---|---|---|---|
| `marcado_para_pular` | `skip`, `xfail`, `only`, `@Ignore`, `markTestSkipped` | confiabilidade | alta |
| `sem_assercao_aparente` | nenhuma asserção reconhecível no corpo | confiabilidade | média |
| `nao_descoberto` | arquivo de teste que o runner não coleta | confiabilidade | alta |
| `espera_fixa` | `sleep`, `setTimeout`, `waitForTimeout` — **atraso zero não conta**: `setTimeout(r, 0)` drena promessas | isolamento | alta |
| `relogio_real` | data/hora real sem congelar | isolamento | média |
| `aleatorio_sem_semente` | aleatório sem semente fixa | isolamento | média |
| `rede_em_unit` | chamada de rede em suíte unitária | isolamento | alta |
| `nome_duplicado` | dois testes com o mesmo nome no arquivo | legibilidade | alta |
| `lento_para_o_tipo` | acima do limite do tipo (unit 1s, integração 10s, e2e 60s) | velocidade | alta |
| `execucao_estourou` | a suíte passou do timeout | velocidade | alta |
| `saida_ilegivel` | não deu para ler a saída do runner | — | alta |

**Confiança média nunca entra em lote automático.** Helper de asserção, matcher custom e `expect`
encadeado fazem `sem_assercao_aparente` errar — por isso ele só vira alta quando um plugin de lint
da stack apontar.

## Inventário e execução contam coisas diferentes

O inventário conta **declarações** de teste; a execução conta **casos**. Num projeto com testes
parametrizados a execução dá um número maior — 127 declarações que viram 181 casos, por exemplo.
Não é erro de contagem: diga qual dos dois você está citando.

## O que o agente julga (sem sinal do script)

Asserção tautológica ou frouxa · mock do próprio sujeito · tudo mockado · asserção em detalhe
interno · nome que não descreve comportamento · teste que testa o framework · vários comportamentos
num teste · caminho crítico sem teste.
