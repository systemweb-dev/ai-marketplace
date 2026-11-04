# Refatorações mecânicas por ferramenta

Use só se a ferramenta **já estiver instalada** no projeto (no manifesto, no lockfile ou no
PATH). Nunca instale sem perguntar. Rode antes em modo de simulação quando houver, mostre o
diff e só então aplique. O ponto de restauração vem antes, como em qualquer etapa.

| Linguagem | Ferramenta | Simular | Aplicar | Serve para |
|---|---|---|---|---|
| PHP | Rector | `vendor/bin/rector process <arq> --dry-run` | `vendor/bin/rector process <arq>` | regras de modernização e renome configuradas no `rector.php` do projeto |
| Python | ruff | `ruff check <arq> --diff` | `ruff check <arq> --fix` | correções que o ruff marca como seguras |
| JS/TS | ESLint | `npx eslint <arq> --fix-dry-run --format json` (o campo `output` traz o arquivo corrigido) | `npx eslint <arq> --fix` | regras com autofix da config do projeto |
| Go | gopls | `gopls rename -d <arq>:#<offset> <novo>` | `gopls rename -w <arq>:#<offset> <novo>` | renomear símbolo com todas as referências |
| Java | OpenRewrite | `mvn rewrite:dryRun` | `mvn rewrite:run` | receitas já declaradas no `pom.xml` |

Sem ferramenta, o agente edita. Renomear símbolo à mão exige grep do nome em código, strings,
configs e templates antes, porque reflexão e injeção de dependência não aparecem no import.
