"""Grafo textual: o símbolo procurado como TEXTO em todo o repositório.

O grafo de import não vê injeção de dependência, reflexão, rota como string
(`"UserController@show"`), facade, template nem wiring por config — e em projeto
legado com framework pesado isso é a MAIOR PARTE do acoplamento.

O erro deste grafo é falso positivo, que aqui é o lado seguro: o do import é
falso negativo, e falso negativo vira "nada depende disso".
"""
import re
from pathlib import Path

from lib.arvore import varrer


def simbolos_de(arvore: list) -> list:
    """Os nomes de arquivo viram os símbolos a procurar."""
    simbolos = set()
    for item in arvore:
        if item['gerado']:
            continue
        base = Path(item['caminho']).name
        for sufixo in ('.blade.php', '.min.js'):
            if base.endswith(sufixo):
                base = base[: -len(sufixo)]
        simbolos.add(Path(base).stem)
    # Dotfile não é símbolo: `Path('.env').stem` devolve `.env`, não '' — então
    # `.env`, `.gitignore` e `.dockerignore` encabeçavam a lista alfabética e
    # gastavam as primeiras vagas do teto de símbolos procurando nome de arquivo de
    # configuração pelo repositório inteiro.
    return sorted(s for s in simbolos if len(s) >= 4 and not s.startswith('.'))


def todas_as_mencoes(raiz, simbolos: list) -> dict:
    """Uma passada pelos arquivos, casando TODOS os símbolos de uma vez.

    Uma varredura por símbolo levava 52 s num repositório de 490 arquivos; com os
    300 símbolos que o inventário pede, num projeto legado de 10 mil arquivos isso
    vira horas. O alvo desta skill é justamente o projeto grande, então a passada
    única não é otimização prematura: é o que torna a skill utilizável.
    """
    raiz = Path(raiz)
    if not simbolos:
        return {}
    # `\b` nas duas pontas: `PedidoCancelado` não é menção a `Pedido`
    padrao = re.compile(r'\b(' + '|'.join(re.escape(s) for s in simbolos) + r')\b')
    achadas = {s: [] for s in simbolos}
    for item in varrer(raiz):
        if item['acima_do_teto'] or item['gerado']:
            continue
        try:
            texto = (raiz / item['caminho']).read_text('utf-8', 'replace')
        except OSError:
            continue
        for n, linha in enumerate(texto.split('\n'), 1):
            for achado in set(padrao.findall(linha)):
                achadas[achado].append({'caminho': item['caminho'], 'linha': n})
    return {s: v for s, v in achadas.items() if v}


def mencoes(raiz, simbolo: str) -> list:
    """Onde um símbolo aparece. Conveniência sobre `todas_as_mencoes`."""
    return todas_as_mencoes(raiz, [simbolo]).get(simbolo, [])
