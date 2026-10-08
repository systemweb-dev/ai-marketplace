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


# Para CONTAR linha a pergunta é outra: o arquivo é texto? `ATIVOS` responde "isto
# é código?", e as duas divergem em dois pontos medidos num projeto real de 1.938
# arquivos — onde 534 arquivos de texto ficaram sem contagem por esta confusão:
#   `config` é texto: `.env.example:12` é citação legítima, e a seção `ambiente` do
#   inventário existe justamente para o `.env`;
#   `svg` é XML: contar nele devolve número verdadeiro, e deixá-lo fora faria a
#   guarda aceitar sem conferir 509 arquivos num projeto só.
# Derivado, e não escrito à mão, porque extensão binária nova acrescentada a
# `ATIVOS` precisa cair fora daqui por padrão.
NAO_E_TEXTO = ATIVOS - {'config', 'svg'}


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


def linhas_por_arquivo(raiz, itens: list, bloco: int = 1 << 16) -> dict:
    """Quantas linhas tem cada arquivo — só onde o número quer dizer algo.

    Existe para a guarda de evidência do `montar.py`, que confere o arquivo citado
    desde sempre e a LINHA nunca: `app/Pedido.php:999999` atravessava intacto, e é
    o erro que o leitor não tem como pegar — ele abre o arquivo, não acha a frase e
    conclui que entendeu errado. O número precisa vir daqui porque o `montar.py` só
    recebe `--dir`: ele nunca vê o projeto em disco, e é essa ignorância que o faz
    reprodutível.

    Três decisões, nesta ordem de importância:

    1. **Binário fica de fora** — e só ele. Contar `\n` num PNG devolve um número, e número
       que não quer dizer nada é pior que ausência: a guarda o usaria para recusar
       uma citação legítima. Ausente significa "não apurado", e a guarda aceita.
    2. **A última linha conta mesmo sem quebra no fim.** `count(b'\n')` subestima
       em um o arquivo que não termina em `\n`, e o erro cai justamente na última
       linha — a mais citada quando alguém aponta o fim de uma função. Recusar a
       citação CORRETA é pior que não conferir.
    3. **Acima do teto não é lido.** O teto existe para a varredura não ler um dump
       de 40 MB; contar linha dele desfaria a economia.

    Medido em quatro projetos reais: 0,26 s para 1.938 arquivos com cache frio,
    0,05 s com cache quente. Lê em blocos e não decodifica — o custo é de I/O, não
    de CPU, e o pico de memória não se move.
    """
    raiz = Path(raiz)
    contagem = {}
    for item in itens:
        if item['acima_do_teto'] or item['linguagem'] in NAO_E_TEXTO:
            continue
        caminho = raiz / item['caminho']
        try:
            with caminho.open('rb') as f:
                total, fim = 0, b''
                while pedaco := f.read(bloco):
                    total += pedaco.count(b'\n')
                    fim = pedaco[-1:]
            contagem[item['caminho']] = total + (1 if fim and fim != b'\n' else 0)
        except OSError:
            continue        # ilegível é não apurado, nunca zero
    return contagem
