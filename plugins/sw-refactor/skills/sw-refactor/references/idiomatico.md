# Idiomático por linguagem e framework

Base para propor padrão quando o projeto não tem nenhum. Antes de propor, com busca na web,
confira a documentação oficial da versão do manifesto e cite `[doc: URL · versão · data]`. Sem
web, use esta tabela e diga "não conferido".

| Linguagem | Nomes | Erros | Validação | Config | Fonte a conferir |
|---|---|---|---|---|---|
| Python | snake_case; classes PascalCase; constantes MAIÚSCULAS (PEP 8) | exceções próprias por domínio; não devolver None como erro | na borda (API/CLI) | um objeto/módulo de settings, não `os.environ` espalhado | PEP 8; docs do framework |
| PHP | métodos camelCase; classes PascalCase (PSR-1/PSR-12) | exceções; não devolver false como erro | Form Request (Laravel) ou camada de validação do framework | `config()`/arquivo de config, não `env()` fora dele (Laravel) | PSR-1, PSR-12; docs do framework |
| JavaScript/TypeScript | camelCase; classes e tipos PascalCase | `throw` de `Error` ou subclasse; em async, rejeição | na borda, com schema (zod/joi/class-validator, o que o projeto usar) | um módulo de config que lê o env uma vez | docs do framework |
| Go | MixedCaps; exportado começa em maiúscula | `error` como último retorno; sem panic em fluxo normal | na borda | struct de config carregada no início | Effective Go |
| Java/Kotlin | camelCase; classes PascalCase | exceções; checked só quando o chamador pode reagir | Bean Validation na borda | `@ConfigurationProperties` (Spring) | docs do framework |
| Ruby | snake_case; classes CamelCase | exceções próprias | no model (Rails) | `Rails.configuration`/credentials | Ruby Style Guide; Rails Guides |

Linguagem fora da tabela: proponha só depois de conferir a documentação oficial; sem web, não
proponha idiomático e deixe a dimensão sem padrão.
