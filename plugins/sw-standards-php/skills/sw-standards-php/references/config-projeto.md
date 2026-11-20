# Config do projeto: `docs/sw-standards/`

A skill grava dois arquivos no projeto, e os dois vão para o git:

| Arquivo | Para quê | Quando muda |
|---|---|---|
| `docs/sw-standards/config.md` | as respostas do projeto e as exceções aceitas | na etapa 0 (passo 8) e quando o dono aceita uma exceção |
| `docs/sw-standards/andamento.md` | as etapas de correção já feitas | no fim de cada etapa, depois do commit |

O relatório de cada auditoria fica em `docs/sw-standards/<data>/relatorio.md`, **fora do git**.

## Como ler

- Toda rodada começa lendo o `config.md`. Se ele não existe, a skill está na primeira vez: faça a etapa 0
  (`references/etapa-0.md`) ou, se o usuário só quer auditar, pergunte as respostas e grave o arquivo.
- As respostas valem mais que o padrão das regras. Exemplo: se o e-mail registrado não é SendGrid,
  `references/regras/datas-dinheiro-pacotes.md` não acusa o pacote registrado.
- Quem varre recebe a tabela de exceções e não acusa o que está nela (`references/subagentes.md`).

## Como gravar

- Pergunte sempre por `AskUserQuestion`, com o padrão como primeira opção.
- **Exceção aceita:** só entra com o "sim" explícito do dono para aquele ponto. Ela leva arquivo e linha, a regra
  (o nome do arquivo em `references/regras/`, sem `.md`), o motivo em uma frase, quem aceitou e a data. Se a linha
  mudar numa correção, atualize a exceção.
- **Andamento:** a etapa 1 é sempre o formatador. Da 2 em diante, é uma etapa por domínio, com todas as regras
  juntas. Estados: `pendente`, `em andamento`, `feito`. A coluna `Commit` leva o hash curto.

## Molde do `config.md`

```markdown
# Padrões deste projeto (sw-standards-php)

## Respostas
- Formato do erro: código específico + frase (padrão) | outro: <descrever>
- E-mail: SendGrid (padrão) | outro: <pacote>
- Multiempresa: não | sim — coluna `<id_company>`, mecanismo `<{Recurso}ExistsMiddleware>`
- PHP: <versão do composer.json/Docker>   · Core: <versão do composer.lock>

## Exceções aceitas
| Arquivo:linha | Regra | Motivo | Quem aceitou | Data |
|---|---|---|---|---|
```

Ao preencher, apague as alternativas que não valem. Exemplo de linha preenchida:

```markdown
- Multiempresa: sim — coluna `id_company`, mecanismo `InvoiceExistsMiddleware`

| app/LogicApp/Helpers/Legacy.php:42 | ruido-defensivo | retorno de API externa que manda "" e 0 | dono | 2026-11-20 |
```

## Molde do `andamento.md`

```markdown
# Andamento da padronização

| Etapa | Domínio | Estado | Data | Commit |
|---|---|---|---|---|
| 0 | preparação | pendente | | |
| 1 | formatador | pendente | | |
```

Acrescente uma linha por domínio quando o relatório definir a ordem de ataque. Exemplos: `2 | erro e segurança`,
`3 | arquitetura`, `4 | código`.
