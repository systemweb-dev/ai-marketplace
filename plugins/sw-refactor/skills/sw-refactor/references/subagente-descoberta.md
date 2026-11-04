# Prompts dos subagentes de descoberta

Despache com `Agent` (`general-purpose`), em paralelo, um por grupo (ou por grupo × módulo em
projeto grande). Até 10 por rodada; passar disso pede pergunta ao usuário. Preencha só os campos
entre colchetes.

## Grupos

| Grupo | Dimensões |
|---|---|
| a. Nomes e layout | caixa de função, classe, constante e arquivo; sufixos e pastas; onde ficam os testes |
| b. Erros e validação | como o erro é lançado e capturado; em que camada a entrada é validada |
| c. Dados e camadas | ORM, repository ou query solta; quem chama quem; lógica fora da camada |
| d. Resposta, log e config | formato de resposta e de log; env direto ou objeto de config; estilo de import |
| e. Complexidade e duplicação | função longa, aninhamento, trecho repetido entre arquivos, abstração sem uso real (fábrica, wrapper ou interface com uma implementação e um chamador; sufixos empilhados como HelperManagerFactory) |

## Prompt-base

```
Você descobre padrões de código num projeto. Só lê: não edite, não crie, não rode nada que
altere arquivos.

Grupo: [GRUPO]
Dimensões: [DIMENSOES]
Escopo de leitura: [ESCOPO]
Regras escritas do projeto (vencem o que o código faz): [REGRAS_ESCRITAS]

Para cada dimensão:
1. Leia arquivos suficientes para contar: todos, se forem até 60; senão, uma amostra de até 60
   espalhada por todas as pastas do escopo, e diga que é amostra.
2. Agrupe em variantes: jeitos diferentes de resolver a mesma coisa.
3. Conte quantos arquivos seguem cada variante. **Unidade:** o arquivo onde a decisão é tomada,
   uma vez por dimensão. Arquivo auxiliar que só existe por causa da variante (a classe Request
   chamada pelo controller, o helper chamado pelo service) não conta: conte o controller ou o
   service que escolheu aquele jeito. Arquivo que só captura ou repassa (o handler que pega a
   exceção que outro lançou) também não conta: conte quem lança ou valida. Variantes de uma
   dimensão somam o total de arquivos de decisão, sem contar nenhum arquivo duas vezes. Arquivo de
   teste não é arquivo de decisão, exceto na dimensão "onde ficam os testes".
4. Dê 3 exemplos `arquivo:linha` por variante (menos, se a variante tiver menos ocorrências).

Ignore formatação: espaço, quebra de linha, ordem de import, aspas. Isso é do formatter.
Marque `muda_contrato: true` só quando mudar o exemplo altera o que alguém **fora deste código**
vê: rota, chave de JSON, status HTTP, mensagem de erro devolvida, coluna, nome chamado por
reflexão ou por outro sistema. Função, método ou parâmetro só chamado dentro do projeto é
`false`, mesmo sendo público: o renome alcança todos os chamadores numa etapa só.
Respeite as regras escritas: o que elas permitem não é desvio.

Responda só com este bloco:

```yaml
grupo: [GRUPO]
lidos: <n>            # arquivos lidos
amostra: <true|false>
dimensoes:
  - nome: <dimensão>
    variantes:
      - descricao: <uma linha>
        arquivos: <n>
        exemplos:
          - local: <arquivo:linha>
            muda_contrato: <true|false>
nao_lidos:
  - arquivo: <caminho>
    motivo: <por quê>
```
```

## Variante "recontagem"

Use quando a variante dominante ficou abaixo de 80%. Mesmo prompt, com uma dimensão só e esta
linha a mais: "Leia todos os arquivos do escopo que tratam desta dimensão, sem amostra."
