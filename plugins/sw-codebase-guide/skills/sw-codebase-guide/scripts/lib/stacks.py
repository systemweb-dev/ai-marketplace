"""Detecta as stacks do projeto.

Projeto poliglota é o caso normal: `/web` com package.json e `/api` com
composer.json são DOIS componentes, e a fronteira entre eles é onde mais se
quebra coisa sem perceber.

Duas lições de rodar contra projeto real, e por isso estão escritas:

1. **Manifesto não é o único sinal.** O próprio marketplace tem 210 arquivos
   Python e nenhum `pyproject.toml`: a regra só-manifesto devolvia duas stacks
   `node` que eram fixture de eval de outra skill, e silenciava a linguagem que é
   de fato o projeto. Pior, o grafo de import decide o que parsear pela lista de
   stacks — então os 210 arquivos não eram nem parseados nem declarados como
   lacuna. Daí o segundo sinal: contagem de extensão.

2. **Diretório de build tem manifesto dentro.** `.next/package.json` virava
   componente, e num projeto Next.js dois dos três componentes eram lixo gerado.
"""
import os
from collections import Counter
from pathlib import Path

MANIFESTOS = {
    'package.json': 'node',
    'composer.json': 'php',
    'go.mod': 'go',
    'pyproject.toml': 'python',
    'requirements.txt': 'python',
    'Cargo.toml': 'rust',
    'Gemfile': 'ruby',
    'pom.xml': 'java',
    'build.gradle': 'java',
}

# Dependência de terceiro, artefato de build e cache. `.next` e companhia entraram
# porque têm manifesto dentro e viravam componente fantasma.
IGNORAR = {
    'vendor', 'node_modules', 'bower_components', '.git', '__pycache__', '.venv',
    'venv', 'dist', 'build', 'out', 'target', 'coverage',
    '.next', '.nuxt', '.svelte-kit', '.turbo', '.cache', '.terraform', '.tox',
    # cache de ferramenta e config de editor: apareciam como EVIDÊNCIA de símbolo no
    # documento (`.ruff_cache/0.16.3/11569727403539023932`), que não ajuda ninguém
    '.ruff_cache', '.pytest_cache', '.mypy_cache', '.claude', '.idea', '.vscode',
}

# Extensão → stack, para a linguagem que domina o projeto sem nenhum manifesto.
EXTENSOES = {
    '.py': 'python', '.php': 'php', '.go': 'go', '.rb': 'ruby',
    '.js': 'node', '.jsx': 'node', '.ts': 'node', '.tsx': 'node', '.vue': 'node',
    '.java': 'java', '.cs': 'dotnet', '.rs': 'rust',
}
MIN_ARQUIVOS = 5      # abaixo disso é script solto, não stack do projeto


def caminhar(raiz):
    """Percorre o projeto podando o que é ignorado, em ordem estável.

    `rglob('*')` materializava 181.975 caminhos para 2.036 úteis num projeto real
    (5 s, 231 MB de pico) porque desce em `node_modules` e `vendor` antes de
    filtrar. A poda em `dirs[:]` corta isso cerca de 90 vezes.
    """
    for pasta, pastas, arquivos in os.walk(raiz):
        pastas[:] = sorted(d for d in pastas if d not in IGNORAR)
        for nome in sorted(arquivos):
            yield Path(pasta) / nome


def detectar(raiz) -> list:
    """Os componentes do projeto: um por manifesto, mais a linguagem não declarada."""
    raiz = Path(raiz)
    achados, vistos, por_extensao, declaradas = [], set(), Counter(), set()

    for arquivo in caminhar(raiz):
        stack = MANIFESTOS.get(arquivo.name)
        if stack is None and arquivo.suffix.lower() == '.csproj':
            stack = 'dotnet'

        if stack is not None:
            caminho = str(arquivo.parent.relative_to(raiz))
            caminho = '.' if caminho == '.' else caminho
            # `pyproject.toml` + `requirements.txt` na mesma pasta é a mesma stack,
            # e o documento imprimia a linha duas vezes.
            if (stack, caminho) not in vistos:
                vistos.add((stack, caminho))
                achados.append({'stack': stack, 'manifesto': arquivo.name,
                                'caminho': caminho, 'por': 'manifesto'})
            declaradas.add(stack)
        else:
            lingua = EXTENSOES.get(arquivo.suffix.lower())
            if lingua:
                por_extensao[lingua] += 1

    for stack, quantos in sorted(por_extensao.items()):
        if stack not in declaradas and quantos >= MIN_ARQUIVOS:
            achados.append({'stack': stack, 'manifesto': None, 'caminho': '.',
                            'por': f'{quantos} arquivos, nenhum manifesto declara'})

    return sorted(achados, key=lambda a: (a['caminho'], a['stack']))
