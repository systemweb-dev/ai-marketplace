"""PHP: o `use` do topo do arquivo, que tem gramática simples e fica sempre lá.

Medido em dois projetos reais: `use X;` são 992 e 1.145 ocorrências, `use … as` é 1
em cada, e as outras três formas não aparecem. Elas entram mesmo assim porque são
sintaxe padrão e custam uma alternância — e o que o extrator não vê sai do
DENOMINADOR da taxa sem avisar, que é pior do que não resolver.
"""
import re

EXTENSOES = ['.php']
BUILTINS = frozenset()      # o `classificar` resolve: nome sem `/` é classe global
ARQUIVO_DE_PASTA = None     # PHP não tem arquivo-de-pasta: um `use` aponta uma classe
NOME_PURO_PODE_SER_INTERNO = False   # `use Exception;` é classe global, nunca do projeto
CONFIGS = [{'arquivo': 'composer.json', 'prefixos': 'autoload.psr-4'}]

SIMPLES = re.compile(
    r'^\s*use\s+(?:function\s+|const\s+)?\\?([A-Za-z_][\w\\]*)\s*(?:as\s+\w+\s*)?;',
    re.M | re.I)
AGRUPADO = re.compile(r'^\s*use\s+\\?([A-Za-z_][\w\\]*)\\\{([^}]+)\}', re.M | re.I)

# `require`/`include` com caminho LITERAL. Sem isto, todo arquivo carregado assim
# parece não ter ninguém apontando para ele — e num projeto PHP real o front
# controller (`www/index.php`) e o `config/Defines.php` apareciam como candidatos a
# código morto, que é o falso positivo mais caro que esta lista pode ter.
# Caminho montado por concatenação (`__DIR__ . $pasta . 'x.php'`) continua invisível:
# o valor da variável não está no texto.
CARREGA = re.compile(
    r'''\b(?:require|include)(?:_once)?\s*\(?\s*(?:__DIR__\s*\.\s*)?['"]([^'"]+\.php)['"]''',
    re.I)


def extrair(texto: str) -> list[str]:
    """Os nomes importados, com `/` no lugar da barra invertida.

    A troca do separador é feita AQUI: a string com `\\` jamais casaria num índice
    construído sobre `/`, e consertar isso no resolvedor exigiria que ele soubesse
    que aquilo é PHP.

    A declaração `namespace` fica de fora de propósito — ela diz onde o arquivo
    MORA, não de quem ele depende, e viraria uma aresta do arquivo para a própria
    pasta.
    """
    achados = [m.group(1) for m in SIMPLES.finditer(texto)]
    for m in CARREGA.finditer(texto):
        caminho = m.group(1)
        # `__DIR__ . '/../x.php'` deixa o caminho começando em `/`: é relativo ao
        # arquivo, não à raiz
        achados.append('./' + caminho.lstrip('/') if not caminho.startswith('.')
                       else caminho)
    for m in AGRUPADO.finditer(texto):
        raiz = m.group(1)
        for item in m.group(2).split(','):
            item = re.split(r'\s+as\s+', item.strip(), flags=re.I)[0].strip()
            if item:
                achados.append(f'{raiz}\\{item}')
    # sem repetição, preservando a ordem: o orquestrador dá `append` em `arestas` por
    # ocorrência, e alvo repetido viraria aresta duplicada no inventário
    return list(dict.fromkeys(a.replace('\\', '/') for a in achados))


def classificar(alvo: str) -> str:
    """`use Exception;` é classe global; com namespace, é qualificado.

    `use` nunca é relativo — é sempre a partir da raiz do namespace. Mas
    `require './config.php'` é, e por isso a categoria existe aqui também.
    """
    if alvo.startswith('.'):
        return 'relativo'
    return 'qualificado' if '/' in alvo else 'nome_puro'
