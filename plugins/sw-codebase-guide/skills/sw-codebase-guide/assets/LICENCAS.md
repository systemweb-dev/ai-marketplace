# Fontes embutidas no relatório

O relatório é um arquivo só, gerado offline (o PDF sai de um Chromium sem rede), então as
fontes viajam dentro dele em base64 — não há CDN nem `@font-face` apontando para fora.

As três são **variáveis**: um arquivo por família cobre todos os pesos usados.

| Família | Arquivo | Papel no relatório | Licença |
|---|---|---|---|
| Bricolage Grotesque | `bricolage-grotesque-latin.woff2` | títulos e números-herói | [OFL 1.1](OFL-bricolagegrotesque.txt) |
| Figtree | `figtree-latin.woff2` | texto corrido e rótulos | [OFL 1.1](OFL-figtree.txt) |
| JetBrains Mono | `jetbrains-mono-latin.woff2` | nome de serviço, comando, número | [OFL 1.1](OFL-jetbrainsmono.txt) |

Todas sob a **SIL Open Font License 1.1**, que permite embutir e redistribuir desde que a
licença acompanhe — é por isso que os três `OFL-*.txt` estão aqui, e não só citados.

- Copyright 2022 The Bricolage Grotesque Project Authors — <https://github.com/ateliertriay/bricolage>
- Copyright 2022 The Figtree Project Authors — <https://github.com/erikdkennedy/figtree>
- Copyright 2020 The JetBrains Mono Project Authors — <https://github.com/JetBrains/JetBrainsMono>

Os arquivos são o **subset latino** servido pelo Google Fonts, sem modificação. Não renomeie
nem altere os arquivos: a OFL reserva os nomes das famílias para as versões originais.

Se algum arquivo faltar, `build_report.py` cai para as fontes do sistema e segue — relatório
não deixa de ser gerado por causa de tipografia.
