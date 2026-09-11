# Calibração do corte de diff — evidência medida

Medido em 2026-09-10. Nomes de repositório e caminhos de arquivo omitidos (repo público).

| Caso | Diff total | Sem ruído | Observação |
|---|---|---|---|
| Feature real, repo de API | 38 KB | 36 KB | 19 arquivos, +739/−24 |
| Feature real, repo de front | **190 KB** | **47 KB** | 142 KB eram só `package-lock.json` |
| Commit único grande (este marketplace) | 173 KB | 146 KB | 24 arquivos, +2.774 |
| 13 commits (este marketplace) | 222 KB | 201 KB | 31 arquivos |

Referência de custo: ~4 bytes por token → 173 KB ≈ 43 mil tokens.

## Decisão derivada
- **Filtro de ruído é decisivo**, não cosmético: no caso de front ele reduz o diff a 25%.
- **Teto proposto: 60 KB de conteúdo no total e 400 linhas por arquivo.** As duas features
  reais cabem inteiras; o maior arquivo de código medido tinha 391 linhas adicionadas.
  Só commits gigantes são cortados — e o corte fica marcado no `fatos.json`.
