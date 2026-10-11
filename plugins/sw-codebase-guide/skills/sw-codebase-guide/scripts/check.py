#!/usr/bin/env python3
"""Confere a interpretação antes de montar o documento.

Roda entre escrever o `interpretation.toml` e rodar o `build.py`. Não escreve
nada, não recusa nada e não muda o documento: imprime o que está fraco e devolve
código 1 para quem roda sem gente olhando.

Faz duas coisas que o `build.py` não faz:

- **adianta a recusa dura.** O `build.py` levanta no PRIMEIRO erro, depois de
  carregar tudo; aqui ela aparece antes, com a mensagem igual, porque é a MESMA
  função que confere. Duas listas divergiriam na primeira regra nova.
- **cobra o que nenhuma recusa cobre:** evidência que aponta a saída da própria
  skill, linha citada sem conteúdo, seção e parte vazias, percurso que não
  atravessa camada, arquivo perigoso e centro do grafo sem uma frase.
"""
import argparse
import json
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
from lib import review  # noqa: E402


def recusa_do_build(inv: dict, base: Path) -> str | None:
    """A mensagem que o `build.py` daria, ou `None`.

    Chama as funções dele, nunca uma cópia: a guarda e o aviso têm de envelhecer
    juntos. E relê o TOML do disco em vez de receber o já lido — o leitor da
    narrativa LIMPA o rótulo dos saltos no próprio dicionário, e passar o mesmo
    objeto faria a conferência depender da ordem em que as duas rodam.
    """
    dados = tomllib.loads((base / 'interpretation.toml').read_text('utf-8'))
    caminhos = set(inv.get('textos') or {}) | set(
        inv.get('caminhos_do_projeto') or [a['caminho'] for a in inv.get('arvore', [])])
    linhas = inv.get('linhas_por_arquivo') or {}
    try:
        build._ler_interpretacao(base / 'interpretation.toml', caminhos, linhas)
        build._ler_narrativa(dados, caminhos, inv.get('textos') or {}, linhas)
    except ValueError as erro:
        return str(erro)
    return None


def relatar(resultado: dict, recusa: str | None, base: Path) -> list:
    L = []
    A = L.append
    c = resultado['contagem']
    A(f'{base / "interpretation.toml"}')
    A(f'  {c["afirmacoes"]} afirmações · {c["blocos"]} blocos de narrativa · '
      f'{c["citacoes"]} citações')
    A('')
    if recusa:
        A('O BUILD VAI RECUSAR')
        A(f'  ● {recusa}')
        A('')
    if resultado['achados']:
        A('O QUE PEDE CONSERTO')
        A('')
    for achado in resultado['achados']:
        A(f'● {achado["titulo"]}')
        for item in achado['itens']:
            A(f'    {item}')
        A(f'  → {achado["conserto"]}')
        A('')
    if resultado['nao_conferido']:
        A('NÃO CONFERIDO')
        for n in resultado['nao_conferido']:
            A(f'  ○ {n["motivo"]}')
        A('')
    if not resultado['achados'] and not recusa:
        # "nada a apontar" nunca é "está certo": as quatro conferências de
        # julgamento não leem o TEXTO, e o pior modo de falha da interpretação
        # continua sendo a frase fluente, verdadeira e inútil
        A('Nada a apontar nesta conferência. Ela olha citação, cobertura e '
          'estrutura —')
        A('não olha se a frase diz algo que o leitor não saberia sozinho.')
    return L


def main() -> int:
    p = argparse.ArgumentParser(
        description='Confere o interpretation.toml antes do build.')
    p.add_argument('--dir', required=True, help='diretório com inventory.json')
    p.add_argument('--projeto', help='raiz do projeto, para conferir o conteúdo '
                                     'das linhas citadas')
    args = p.parse_args()

    base = Path(args.dir).resolve()
    inventario, interpretacao = base / 'inventory.json', base / 'interpretation.toml'
    if not inventario.exists():
        print(f'não achei {inventario} — rode scan.py antes', file=sys.stderr)
        return 2
    if not interpretacao.exists():
        print(f'não achei {interpretacao} — escreva a interpretação antes',
              file=sys.stderr)
        return 2

    inv = json.loads(inventario.read_text('utf-8'))
    try:
        dados = tomllib.loads(interpretacao.read_text('utf-8'))
    except tomllib.TOMLDecodeError as erro:
        print(f'interpretation.toml não é TOML válido: {erro}', file=sys.stderr)
        return 2

    projeto = Path(args.projeto).resolve() if args.projeto else None
    if projeto and not projeto.is_dir():
        print(f'--projeto não é um diretório: {projeto}', file=sys.stderr)
        return 2

    resultado = review.conferir(inv, dados, projeto)
    recusa = recusa_do_build(inv, base)
    print('\n'.join(relatar(resultado, recusa, base)))
    # 1 é "tem o que consertar", não "falhei": quem roda sem gente olhando precisa
    # distinguir isso de 2, que é não ter conseguido conferir
    return 1 if (resultado['achados'] or recusa) else 0


if __name__ == '__main__':
    raise SystemExit(main())
