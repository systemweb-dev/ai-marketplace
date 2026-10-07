"""As áreas do projeto, por agrupamento de diretórios da árvore.

NÃO usa a detecção por convenção de caminho (`superficie.py`): ela marcou 29
"rotas" que eram controllers num projeto PHP e não achou as 20 áreas do App Router
num Next.js. Ela continua valendo para a seção "Superfície pública", onde sai
marcada como dedução — mas não pode decidir o escopo, que é a primeira tela.

Os limiares têm número porque, sem número, cada projeto geraria um menu diferente
por motivo que ninguém sabe explicar. Os dois casos-âncora são o monorepo por
justaposição (áreas no nível 1) e o Next.js (áreas em `src/app/(app)/`).

**Calibração contra seis projetos reais (07/10) mudou o desenho em três pontos**,
e cada um nasceu de um menu que não servia:

1. **Área não atravessa fronteira de stack.** No monorepo, `admin/` tem o próprio
   `package.json` e é um sistema inteiro: descer dentro dele devolveria os
   componentes de uma aplicação misturados com as rotas de outra. Pasta com
   manifesto próprio é átomo — vira área e não se abre.
2. **Pasta grande que se abre em três é substituída pelos filhos.** O corte global
   parava no nível 1 e oferecia `src` num projeto de 630 arquivos. O teste-âncora
   passava porque o fixture só tinha `src/app/(app)/*`; projeto real tem `tests/`
   e `docs/` ao lado, e com eles o corte nunca descia. É o defeito que a suíte
   verde escondia.
3. **Lixo de ferramenta não é área.** `.playwright-mcp` entrou num menu real.
"""
from collections import Counter
from pathlib import Path

from lib.arvore import eh_codigo, linguagem_de

DOMINANTE = 0.80        # um filho com ≥ 80% dos arquivos: desce mais
MIN_FILHOS = 3          # a partir de 3 filhos acima do piso, corta aqui
PISO_ARQUIVOS = 3       # abaixo disso não é área, é pasta solta
TETO_AREA = 120         # área maior que isto, que se abre em 3, é aberta
COBERTURA = 0.70        # os filhos precisam responder por tanto do pai

# Pasta que nenhum projeto quer ver no menu de escopo. Não é a mesma lista do
# `stacks.IGNORAR` (que poda dependência e build antes de contar): esta é de
# saída de ferramenta que sobrevive à poda e já apareceu num menu real.
LIXO = {'.playwright-mcp', '.claude', '.github', '.vscode', '.idea', '.husky'}


def _conta_por_prefixo(arvore: list) -> Counter:
    contagem = Counter()
    for item in arvore:
        if item['gerado']:
            continue
        partes = item['caminho'].replace('\\', '/').split('/')
        if partes[0] in LIXO:
            continue
        for i in range(1, len(partes)):
            contagem['/'.join(partes[:i])] += 1
    return contagem


def _filhos(contagem: Counter, pai: str) -> list:
    prefixo = f'{pai}/' if pai else ''
    nivel = len(prefixo.split('/')) - 1 if prefixo else 0
    return [c for c in contagem
            if c.startswith(prefixo) and len(c.split('/')) == nivel + 1]


def _acima_do_piso(contagem: Counter, pai: str) -> list:
    return [f for f in _filhos(contagem, pai) if contagem[f] >= PISO_ARQUIVOS]


def _descer(contagem: Counter, pai: str, atomos: frozenset) -> list:
    """Com o que substituir `pai` — ou `[pai]`, quando ele não deve se abrir."""
    if pai and pai in atomos:
        return [pai]                      # fronteira de stack: não se abre
    filhos = _acima_do_piso(contagem, pai)
    if not filhos:
        return [pai] if pai else []
    # COBERTURA: os filhos precisam responder pela maior parte do pai. Sem isto,
    # uma pasta com 180 arquivos soltos no topo e três subpastas de 4 era cortada
    # em três áreas minúsculas, e os 180 arquivos sumiam do menu inteiro.
    if pai and sum(contagem[f] for f in filhos) < COBERTURA * contagem[pai]:
        return [pai]
    if len(filhos) >= MIN_FILHOS:
        return sorted(filhos)
    dominante = max(filhos, key=lambda f: contagem[f])
    # O denominador é a soma DOS FILHOS, não o total do projeto. Com o total,
    # arquivos soltos na raiz diluíam a fração: `src` com 9 de 12 arquivos dava
    # 0,75 < 0,80 e a descida parava em `src`, devolvendo uma área só.
    no_nivel = sum(contagem[f] for f in filhos)
    if contagem[dominante] >= DOMINANTE * no_nivel:
        return _descer(contagem, dominante, atomos)
    return sorted(filhos)


def _abrir_as_grandes(contagem: Counter, caminhos: list, atomos: frozenset) -> list:
    """Substitui a área grande demais pelo que o `_descer` encontra dentro dela.

    É o que leva de `src` às áreas do App Router. Sem isto o menu de um projeto de
    630 arquivos oferecia a pasta `src` inteira como uma opção — e o teste-âncora
    não pegava, porque o fixture não tinha `tests/` nem `docs/` ao lado para fazer
    o corte parar no nível 1.
    """
    abertos, fila, vistos = [], list(caminhos), set()
    while fila:
        c = fila.pop(0)
        if c in vistos:
            continue
        vistos.add(c)
        if c in atomos or contagem[c] <= TETO_AREA:
            abertos.append(c)
            continue
        dentro = _descer(contagem, c, atomos)
        if dentro == [c]:
            abertos.append(c)
        else:
            fila = dentro + fila
    return sorted(set(abertos))


def detectar(arvore: list, recentes: dict | None, stacks: list | None = None) -> list:
    """As áreas, ordenadas pelo que foi mais mexido — ou por tamanho, sem git.

    `stacks` é a seção homônima do inventário. Quem tem manifesto próprio vira
    átomo: é um sistema inteiro, e abrir por dentro mistura as duas aplicações.
    """
    # Só arquivo de CÓDIGO conta. O menu pergunta qual parte do SISTEMA documentar,
    # e num projeto real oito das doze áreas oferecidas eram subpastas de `docs/` —
    # `docs/product` tinha 47 arquivos e zero código. Ninguém pede para entender a
    # área de marketing, e contar markdown junto ainda fazia a pasta de documentação
    # parecer maior que o serviço.
    codigo = [a for a in arvore if eh_codigo(linguagem_de(Path(a['caminho'])))]
    contagem = _conta_por_prefixo(codigo)
    atomos = frozenset(
        s['caminho'] for s in (stacks or [])
        if s.get('manifesto') and s.get('caminho') not in ('', '.')
    )
    caminhos = _abrir_as_grandes(contagem, _descer(contagem, '', atomos), atomos)

    # `commits_recentes: 0` se lê como *ninguém mexe nisso há 90 dias*. Sem medição
    # nenhuma — raiz sem git — nada disso foi apurado, e o menu anunciava zero nas
    # seis áreas de um monorepo vivo. Não medido é `None`; zero medido continua zero,
    # que é informação apurada e não se joga fora.
    areas = [{'caminho': c, 'arquivos': contagem[c],
              'commits_recentes': recentes.get(c, 0) if recentes else None}
             for c in caminhos]
    if recentes:
        areas.sort(key=lambda a: (-a['commits_recentes'], -a['arquivos'], a['caminho']))
    else:
        areas.sort(key=lambda a: (-a['arquivos'], a['caminho']))
    return areas
