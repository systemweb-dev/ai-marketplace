"""As fontes textuais do projeto: README, CLAUDE.md, docs, ADR, tradução.

É a única seção do inventário que carrega CONTEÚDO. O resto só leva caminho,
contagem e nome de chave — e o `varrer.py` diz isso por escrito, porque o
`inventory.json` é commitado.

Por isso o conteúdo passa por `redact.redigir` **campo a campo, antes de
serializar**. Nunca sobre o JSON pronto: isso já quebrou o arquivo uma vez,
transformando `"AuthController": [` em `"AuthController": ***`.

Existe para a parte "o que o produto faz" do documento humano. Sem esta seção o
agente só acha o README se lembrar de procurar — e foi um `CLAUDE.md` que
respondeu, num teste real, o que entrevista nenhuma responderia.
"""
import re
from fnmatch import fnmatch
from pathlib import Path

from lib import redact

TETO_BYTES = 64 * 1024       # por arquivo
TETO_TOTAL = 384 * 1024      # da seção inteira
TETO_ARQUIVOS = 32           # além disto a seção enterra o que importa

# Dossiê de trabalho: `docs/specs/<data>-<slug>/plan.md`, `docs/plans/…`,
# `referencias/…`. NÃO é fonte textual sobre o sistema — descreve UM trabalho
# passado, no detalhe de quem ia executá-lo. Medido num monorepo real: 68 fontes e
# 1,4 MB, das quais 60 eram dossiê, e os seis maiores arquivos eram planos de
# implementação. O `inventory.json` é commitado, e quem o lê para responder "o que o
# produto faz" recebia arqueologia de task no lugar de três READMEs.
DOSSIE = re.compile(r'(?i)(^|/)(specs?|plans?|planos|referencias?|references)/')

# Classe 0 responde "o que o produto faz"; classe 1 pode responder.
PRIMARIA = re.compile(
    r'(?i)^(readme|claude|agents|contributing|changelog|arquitetura|architecture)')

# Nome ou caminho que denuncia fonte textual. `docs/` é recursivo de propósito:
# `docs/adr/0001-escolha-do-banco.md` é o caso real.
#
# **Os padrões valem em qualquer profundidade, não só na raiz.** Ancorados em `^`,
# um monorepo real com seis READMEs na árvore entregou ZERO fontes textuais: o
# README de cada aplicação mora em `admin/`, `api/`, `website/`. Como "propósito só
# com fonte textual" é regra desta skill, a frase mais valiosa do documento virava
# lacuna por causa de um acento circunflexo.
#
# O prefixo é `(?:^|.*/)` e não `.*`: a barra obriga o trecho a começar no início de
# um segmento, senão `src/mydocs/` passaria por pasta de documentação e
# `oldreadme.md` por README.
NIVEL = r'(?:^|.*/)'

PADROES = [
    re.compile(r'(?i)' + NIVEL + r'readme[^/]*\.(md|txt|rst)$'),
    re.compile(r'(?i)' + NIVEL + r'(claude|agents|contributing|changelog|arquitetura|architecture)\.md$'),
    re.compile(r'(?i)' + NIVEL + r'docs?/.*\.(md|txt|rst|adoc)$'),
    re.compile(r'(?i)' + NIVEL + r'adrs?/.*\.md$'),
    re.compile(r'(?i).*\.adr\.md$'),
    re.compile(r'(?i)' + NIVEL + r'(locales?|lang|i18n|translations?)/.*\.(json|ya?ml|po|ts|js)$'),
]


# Pasta de ferramenta que a árvore poda — ela não é código, não é área e encheria a
# contagem de arquivos — mas onde mora, em muitos projetos, a ÚNICA documentação
# escrita. Num projeto PHP real a única fonte era `.claude/CLAUDE.md`, e `textos`
# vinha vazio: a regra "propósito só com fonte textual" apagava um projeto
# documentado. Só o primeiro nível e o `docs/`: `.claude/skills/` é de outro assunto.
OCULTAS = ('.claude/*.md', '.claude/*.txt', '.claude/docs/**/*.md',
           '.claude/rules/*.md', '.github/*.md', '.github/docs/**/*.md')


def eh_fonte_textual(caminho: str) -> bool:
    """Este caminho é fonte textual sobre o SISTEMA?

    A pergunta tem o sistema dentro de propósito: um `plan.md` é documento legítimo
    e não é resposta. A lista branca do `varrer.py --areas` usa esta mesma função,
    então o que sai daqui também para de ser aberto na fase barata.
    """
    normal = caminho.replace('\\', '/')
    if DOSSIE.search('/' + normal):
        return False
    if any(fnmatch(normal, padrao) for padrao in OCULTAS):
        return True
    return any(p.match(normal) for p in PADROES)


def _ordem_de_leitura(caminho: str) -> tuple:
    """Quem é lido primeiro quando o teto da seção não cabe em todos.

    Por CLASSE antes de tudo: em ordem alfabética, um `docs/aaa.md` de 300 KB come o
    orçamento e o README fica de fora — justamente o arquivo que a seção existe para
    entregar. Depois pela profundidade (README da raiz antes do de um pacote) e, por
    fim, pelo caminho, para a saída não depender da ordem do sistema de arquivos.
    """
    nome = caminho.rsplit('/', 1)[-1]
    classe = 0 if (PRIMARIA.match(nome) or '/adr' in ('/' + caminho.lower())
                   or nome.lower().endswith('.adr.md')) else 1
    return (classe, caminho.count('/'), caminho)


def coletar(raiz, arvore: list) -> dict:
    """O conteúdo das fontes textuais, redigido, com teto e em ordem estável.

    **O caminho de toda fonte entra; o conteúdo entra até o teto.** O que ficou de
    fora continua na lista com `omitido` e o motivo, porque é a lista completa que
    permite a quem lê abrir o arquivo à mão — cortar em silêncio seria "não apurado"
    com cara de "não existe", que é exatamente o que esta skill promete não fazer.
    """
    raiz = Path(raiz)
    caminhos = [i['caminho'] for i in arvore if eh_fonte_textual(i['caminho'])]
    caminhos += _ocultas(raiz)
    achados, gasto, lidos = {}, 0, 0

    for caminho in sorted(caminhos, key=_ordem_de_leitura):
        if lidos >= TETO_ARQUIVOS or gasto >= TETO_TOTAL:
            achados[caminho] = {
                'conteudo': '', 'cortado': False, 'omitido': True,
                'motivo': (f'a seção parou em {TETO_ARQUIVOS} arquivos e '
                           f'{TETO_TOTAL // 1024} KB; abra o arquivo se precisar dele'),
            }
            continue
        try:
            bruto = (raiz / caminho).read_text('utf-8', 'replace')
        except OSError:
            continue
        conteudo = _redigir_por_linha(bruto[:TETO_BYTES])
        achados[caminho] = {'conteudo': conteudo, 'cortado': len(bruto) > TETO_BYTES}
        gasto += len(conteudo)
        lidos += 1

    # a ordem do JSON é a do caminho, não a de leitura: o arquivo precisa dar diff
    return {c: achados[c] for c in sorted(achados)}


def _ocultas(raiz: Path) -> list:
    """A documentação que mora em pasta podada da árvore."""
    achados = set()
    for padrao in OCULTAS:
        for caminho in raiz.glob(padrao):
            if caminho.is_file():
                achados.add(caminho.relative_to(raiz).as_posix())
    return sorted(achados)


def _redigir_por_linha(texto: str) -> str:
    """Redige LINHA A LINHA, não o texto inteiro. Dois motivos medidos:

    1. O padrão de par do `redact` tem `\\s*` entre a chave e o separador, e ele
       atravessa quebra de linha. Sobre o texto inteiro,
       `'Configure o acesso:\\n\\nGITHUB_TOKEN=ghp_…'` casa `chave=acesso` e
       `valor=GITHUB_TOKEN=ghp_…` — e a CHAVE some junto com o valor.
    2. Backtracking catastrófico: 65 KB de texto sem separador levaram 77 s.
       Linha a linha, prosa real sai em centésimos.
    """
    return '\n'.join(redact.redigir(linha) for linha in texto.split('\n'))
