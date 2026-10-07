"""Árvore de arquivos do projeto: o que existe, de que tamanho e em que linguagem.

A ordem é estável por desenho — o documento precisa dar diff, e ordem instável
tornaria duas rodadas diferentes sem nada ter mudado.
"""
from pathlib import Path

from lib.stacks import IGNORAR, caminhar

LINGUAGENS = {
    '.php': 'php', '.py': 'python', '.js': 'javascript', '.jsx': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript', '.go': 'go', '.rb': 'ruby',
    '.java': 'java', '.cs': 'csharp', '.rs': 'rust', '.sql': 'sql',
    '.html': 'html', '.css': 'css', '.scss': 'css', '.vue': 'vue',
    '.blade.php': 'blade', '.twig': 'twig', '.yml': 'yaml', '.yaml': 'yaml',
    '.json': 'json', '.toml': 'toml', '.md': 'markdown', '.sh': 'shell',
}

# Sufixo que denuncia arquivo gerado: ele infla a contagem e polui o grafo.
GERADOS = ('.min.js', '.min.css', '.lock', '.map', '-lock.json', '.pyc', '.generated.ts')


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
