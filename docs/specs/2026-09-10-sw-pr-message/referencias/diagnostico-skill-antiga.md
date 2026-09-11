# Diagnóstico da sw-git-pr-generator (a skill substituída)

O conteúdo da skill não é arquivado aqui (repositório público; skill só é publicada a pedido).

1. **Lista commits, não mudanças** — um bullet por commit, com hash; `wip` e `ajuste do review` viram ruído.
2. **Lê só o assunto** (`%s`) — ignora corpo e diff; commit vago sai vago.
3. **Base em ordem fixa** `main → master → develop` — erra em fluxo com `develop` (ver `deteccao-de-base.md`).
4. **Título = nome da branch** (`feature/x`), que não é título de PR.
5. **Grava `PR-MESSAGE.md` na raiz** sem proteção — pode entrar num commit.
6. **`chore`, `ci`, `build` e `style` viram "Melhorias"** — engana quem lê.
7. **Faltam** "como testar" e as informações de hotfix (causa, impacto, rollback).
8. **Diagrama Mermaid** é uma árvore de títulos de commit — informa pouco.
