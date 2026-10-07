"""Grafo de dependências por import — ferramenta nativa primeiro.

Regex sobre import erra para o lado perigoso: resolver a STRING do import em
ARQUIVO exige `paths` do tsconfig, PSR-4 do composer, workspaces e barrel. Sem
isso as arestas ficam penduradas e o grafo perde nó em silêncio.

Neste plano só Python tem caminho nativo (o `ast` da stdlib, sempre presente).
As outras stacks aparecem como INDISPONÍVEL com motivo — nunca como grafo vazio,
porque grafo vazio se lê como "nada depende de nada".
"""
import ast
from pathlib import Path

from lib.arvore import varrer


def _indice(arquivos) -> dict:
    """Indexa cada módulo por TODOS os sufixos do seu caminho pontilhado.

    A chave ancorada na raiz (`plugins/x/scripts/lib/config.py` →
    `plugins.x.scripts.lib.config`) nunca casa com o import que o código escreve
    (`from lib.config import ...`), porque é `scripts/` que entra no `sys.path`.
    Num projeto Python real isso dava ZERO arestas com 243 imports locais.

    Sufixo ambíguo — dois arquivos terminando igual — **não resolve**. Aresta
    errada é pior que aresta faltando: a falta é coberta pelo grafo textual, e a
    errada manda alguém mexer no arquivo errado.
    """
    por_sufixo = {}
    for caminho in arquivos:
        p = Path(caminho)
        partes = p.parent.parts if p.name == '__init__.py' else p.with_suffix('').parts
        for i in range(len(partes)):
            por_sufixo.setdefault('.'.join(partes[i:]), set()).add(caminho)
    return {chave: destinos.pop() for chave, destinos in por_sufixo.items()
            if len(destinos) == 1}


def _arestas_python(raiz, arquivos) -> list:
    modulos = _indice(arquivos)

    arestas = []
    for caminho in arquivos:
        try:
            arvore_ast = ast.parse((raiz / caminho).read_text('utf-8', 'replace'))
        except (SyntaxError, ValueError, OSError):
            continue          # arquivo quebrado não derruba a varredura inteira
        alvos = set()
        for no in ast.walk(arvore_ast):
            if isinstance(no, ast.Import):
                alvos.update(a.name for a in no.names)
            elif isinstance(no, ast.ImportFrom):
                base = no.module or ''
                if no.level:
                    # Import relativo (`from .x import Y`) é a forma NORMAL dentro de
                    # um pacote. Ignorá-lo faria o grafo de um projeto bem organizado
                    # sair MAIS vazio que o de um bagunçado — o inverso da verdade.
                    # Nível 1 é o pacote do próprio arquivo; cada nível a mais sobe um.
                    partes = Path(caminho).parent.parts
                    if no.level - 1 > len(partes):
                        continue      # sobe acima da raiz: não há como resolver
                    pacote = partes[:len(partes) - (no.level - 1)]
                    base = '.'.join([*pacote, base] if base else pacote)
                if not base:
                    continue
                alvos.add(base)
                alvos.update(f'{base}.{a.name}' for a in no.names)
        for alvo in alvos:
            destino = modulos.get(alvo)
            if destino and destino != caminho:
                arestas.append({'de': caminho, 'para': destino})
    return sorted(arestas, key=lambda a: (a['de'], a['para']))


def grafo(raiz, stacks: list) -> dict:
    """Arestas de import do que deu para resolver, e o motivo do que não deu."""
    raiz = Path(raiz)

    # Projeto sem manifesto nenhum acontece (centenas de arquivos PHP e nenhum
    # composer.json), e aí a detecção de stack devolve lista vazia. Sair daqui com
    # as duas listas vazias seria SILÊNCIO: quem lê conclui que nada depende de
    # nada, quando a verdade é que nada foi sequer tentado.
    if not stacks:
        return {'arestas': [], 'indisponivel': [{
            'stack': '(nenhuma)',
            'motivo': 'nenhuma stack foi detectada — nenhum manifesto encontrado no '
                      'projeto, então não há resolvedor nativo para aplicar; isto NÃO '
                      'significa que nada depende de nada',
        }]}

    arquivos = [i['caminho'] for i in varrer(raiz) if not i['gerado']]

    arestas, indisponivel = [], []
    for componente in {s['stack'] for s in stacks}:
        if componente == 'python':
            py = [c for c in arquivos if c.endswith('.py')]
            arestas.extend(_arestas_python(raiz, py))
        else:
            indisponivel.append({
                'stack': componente,
                'motivo': f'nesta versão só há resolução nativa para python; '
                          f'o acoplamento de {componente} aparece pelo grafo textual',
            })
    return {'arestas': arestas,
            'indisponivel': sorted(indisponivel, key=lambda i: i['stack'])}
