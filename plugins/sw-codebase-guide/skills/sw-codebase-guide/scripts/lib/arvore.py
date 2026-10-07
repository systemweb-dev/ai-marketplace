"""Árvore de arquivos do projeto: o que existe, de que tamanho e em que linguagem.

A ordem é estável por desenho — o documento precisa dar diff, e ordem instável
tornaria duas rodadas diferentes sem nada ter mudado.
"""
from pathlib import Path

from lib.stacks import IGNORAR, caminhar

# O vocabulário de "o que é código" mora AQUI, junto de quem atribui a linguagem, e
# não em cada emissor: o conjunto já existiu em três cópias, e os dois documentos
# chegaram a discordar sobre se um `.md` é código.
ATIVOS = {'png', 'svg', 'jpg', 'jpeg', 'gif', 'ico', 'webp', 'woff', 'woff2',
          'ttf', 'eot', 'mp4', 'pdf', 'zip', 'config'}

# prosa e dado: contam em "do que é feito" (saber que um projeto tem 73 markdowns
# diz algo), mas NÃO em "arquivos maiores", que pergunta onde está a massa do
# CÓDIGO. Sem este corte, os cinco maiores eram todos documento, e o bloco
# respondia outra pergunta — num projeto real o topo era um plano de 253 KB.
NAO_E_CODIGO = {'markdown', 'text', 'rst', 'adoc', 'json', 'yaml', 'yml',
                'toml', 'xml', 'csv', 'ini', 'tsbuildinfo', 'lock'}


def eh_codigo(linguagem: str) -> bool:
    """Uma definição de código, para o documento inteiro.

    O cabeçalho contava `.md` e `.yaml` como código e o bloco de arquivos maiores
    dizia que não eram — duas definições na mesma página, e o conjunto `ATIVOS` em
    três cópias, uma por emissor.
    """
    return linguagem not in ATIVOS and linguagem not in NAO_E_CODIGO

LINGUAGENS = {
    '.php': 'php', '.py': 'python', '.js': 'javascript', '.jsx': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript', '.go': 'go', '.rb': 'ruby',
    '.java': 'java', '.cs': 'csharp', '.rs': 'rust', '.sql': 'sql',
    '.html': 'html', '.css': 'css', '.scss': 'css', '.vue': 'vue',
    '.blade.php': 'blade', '.twig': 'twig', '.yml': 'yaml', '.yaml': 'yaml',
    '.json': 'json', '.toml': 'toml', '.md': 'markdown', '.sh': 'shell',
}

# Sufixo que denuncia arquivo gerado: ele infla a contagem e polui o grafo.
# `.d.ts` e `.stories.*` não são código que alguém mantém, e são fabricantes de
# sufixo duplicado: `Botao.d.ts` ao lado de `Botao.ts` cria ambiguidade artificial
# que derruba a taxa de resolução sem nada estar errado.
GERADOS = ('.min.js', '.min.css', '.lock', '.map', '-lock.json', '.pyc', '.generated.ts',
           '.tsbuildinfo', '.snap', '.pb.go', '_pb2.py', '.d.ts',
           '.stories.ts', '.stories.tsx', '.stories.js', '.stories.jsx', '.stories.vue')


def linguagem_de(caminho: Path) -> str:
    nome = caminho.name.lower()
    # sufixo mais LONGO primeiro: na ordem de inserção `.php` vencia `.blade.php`
    # e a linguagem `blade` nunca era atribuída
    for sufixo, lingua in sorted(LINGUAGENS.items(), key=lambda kv: -len(kv[0])):
        if nome.endswith(sufixo):
            return lingua
    # Dotfile composto (`.env.production`, `.env.teste`) tem `suffix == '.production'`,
    # e o fallback inventava a linguagem "production".
    if caminho.name.startswith('.'):
        return 'config'
    return caminho.suffix.lstrip('.').lower() or 'sem-extensao'


def varrer(raiz, teto_bytes: int = 1_000_000) -> list:
    """Lista os arquivos do projeto, em ordem estável."""
    raiz = Path(raiz)
    itens = []
    # `caminhar` poda as pastas ignoradas durante a descida. `rglob('*')` descia em
    # `node_modules` e `vendor` para só então filtrar: 181.975 caminhos materializados
    # para 2.036 úteis num projeto real, 5 s e 231 MB de pico.
    for arquivo in caminhar(raiz):
        if not arquivo.is_file() or arquivo.is_symlink():
            continue
        tamanho = arquivo.stat().st_size
        itens.append({
            'caminho': str(arquivo.relative_to(raiz)),
            'bytes': tamanho,
            'linguagem': linguagem_de(arquivo),
            'gerado': arquivo.name.lower().endswith(GERADOS),
            'acima_do_teto': tamanho > teto_bytes,
        })
    return sorted(itens, key=lambda i: i['caminho'])
