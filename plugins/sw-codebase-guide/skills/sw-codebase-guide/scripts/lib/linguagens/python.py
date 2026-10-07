"""Python: o `ast` da stdlib, que sempre está presente."""
import ast

EXTENSOES = ['.py']
# Vazio de propósito: aqui quem separa interno de externo é o ÍNDICE, não uma
# lista. `import json` não casa com arquivo nenhum do projeto e por isso é externo —
# a regra está no orquestrador, que conta como externo o nome puro que não casou,
# na linguagem que permite nome puro interno. Uma lista de stdlib aqui seria uma
# segunda verdade para manter, e não cobriria pacote de terceiro.
BUILTINS = frozenset()
CONFIGS = []                    # Python não declara mapeamento de caminho em JSON
ARQUIVO_DE_PASTA = '__init__'   # `from pacote import X` -> `pacote/__init__.py`
NOME_PURO_PODE_SER_INTERNO = True   # layout plano: `from pedido import Pedido`


def extrair(texto: str) -> list[str]:
    """Os módulos importados, como CAMINHO: ponto vira `/`, e o import relativo vira
    `./` e `../`.

    As duas traduções são feitas AQUI e não no resolvedor. `from .irmao import x` com
    o ponto cru seria lido como nome de arquivo (`pasta/.irmao`) e o import ficaria
    pendurado; e fazer o resolvedor saber que em Python o separador é ponto seria um
    `if linguagem ==` disfarçado de detalhe.
    """
    try:
        arvore = ast.parse(texto)
    except (SyntaxError, ValueError, RecursionError):
        # `ValueError` é o que o `ast` levanta para byte nulo antes do 3.12, e a
        # skill roda com o `python3` que a máquina tiver: capturar só `SyntaxError`
        # derrubaria a varredura inteira por causa de um arquivo
        return []
    achados = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            achados += [a.name.replace('.', '/') for a in no.names]
        elif isinstance(no, ast.ImportFrom):
            modulo = (no.module or '').replace('.', '/')
            # O NOME importado também é candidato: `from lib import arvore` pode ser
            # o módulo `lib/arvore`, e não só um símbolo dentro de `lib`. Medido:
            # 35% das arestas Python desta skill vinham só desse candidato, e
            # `scripts/lib/` não tem `__init__.py` — sem ele o `varrer.py` ficaria
            # isolado no grafo do próprio projeto. `*` fica de fora: não é nome.
            nomes = [a.name for a in no.names if a.name != '*']
            if not no.level:
                if modulo:
                    achados.append(modulo)
                    achados += [f'{modulo}/{nome}' for nome in nomes]
            else:
                # Nível 1 é o pacote do próprio arquivo (`./`); cada nível a mais sobe
                # um (`../`). O `./` sai quando há subida: `./../pai` aponta o mesmo
                # lugar que `../pai` e o resolvedor normaliza os dois igual — a forma
                # curta é escolhida para a saída do extrator ser canônica, porque é
                # ela que entra no `inventory.json`, que precisa dar diff.
                prefixo = './' if no.level == 1 else '../' * (no.level - 1)
                base = prefixo + modulo
                achados.append(base)
                achados += [f'{base}/{nome}' if modulo else f'{base}{nome}'
                            for nome in nomes]
    # sem repetição, preservando a ordem: o orquestrador dá `append` em `arestas` por
    # ocorrência, então alvo repetido viraria aresta duplicada no inventário e
    # dependente contado duas vezes no ranking
    return list(dict.fromkeys(achados))


def classificar(alvo: str) -> str:
    if alvo.startswith('.'):
        return 'relativo'
    return 'qualificado' if '/' in alvo else 'nome_puro'
