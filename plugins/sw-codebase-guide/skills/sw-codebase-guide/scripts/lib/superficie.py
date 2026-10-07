"""Superfície pública por CONVENÇÃO DE CAMINHO.

Sem TOML de stack não dá para ler a rota em si — mas dá para dizer onde elas
moram, e isso já orienta quem chega no projeto. Por isso tudo aqui sai como
DEDUÇÃO, com o critério junto: pasta chamada `routes/` é indício, não prova, e
quem lê precisa poder discordar.
"""
from pathlib import Path

from lib.arvore import varrer

# Trecho de caminho → que tipo de superfície ele sugere. A ordem importa:
# `app/Console/Commands` casa comando antes de qualquer regra mais larga.
CONVENCOES = [
    ('console/commands', 'comando'),
    ('app/commands', 'comando'),
    ('management/commands', 'comando'),
    ('migrations', 'migration'),
    ('app/jobs', 'job'),
    ('jobs', 'job'),
    ('queues', 'job'),
    ('app/listeners', 'job'),
    ('workers', 'job'),
    ('routes', 'rota'),
    ('app/http/controllers', 'rota'),
    ('controllers', 'rota'),
    ('app/api', 'rota'),
    ('pages/api', 'rota'),
]


def detectar(raiz) -> list:
    """Onde a superfície pública parece morar, e por qual critério."""
    raiz = Path(raiz)
    achados = []
    for item in varrer(raiz):
        if item['gerado']:
            continue
        caminho = item['caminho'].replace('\\', '/').lower()
        pasta = caminho.rsplit('/', 1)[0] if '/' in caminho else ''
        # Casamento por SEGMENTO de caminho, com as barras como fronteira. A versão
        # anterior tinha três condições e nenhuma pegava `src/app/api/usuarios/route.ts`
        # — trecho com barra só casava se o arquivo estivesse direto na pasta, e um
        # projeto Next.js inteiro saía sem superfície nenhuma.
        # A fronteira também é o que impede `src/routes-helper/` de casar `routes`.
        alvo = '/' + pasta + '/'
        for trecho, tipo in CONVENCOES:
            if '/' + trecho + '/' in alvo:
                achados.append({
                    'tipo': tipo,
                    'caminho': item['caminho'],
                    'por': trecho + '/',
                })
                break
    return sorted(achados, key=lambda a: (a['tipo'], a['caminho']))
