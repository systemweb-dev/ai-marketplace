#!/usr/bin/env python3
"""Apura os fatos de um projeto e grava `inventory.json`.

É DETERMINÍSTICO e regenerável: sem carimbo de tempo, ordem estável em tudo. É o
que permite ao documento dar diff, e é por isso que o agente NÃO escreve aqui —
ele escreve no `interpretation.toml`, que é outro arquivo com outro dono.

Lê o projeto; não altera nada dele. Só escreve no diretório de saída.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import arvore as mod_arvore          # noqa: E402
from lib import areas, historia, imports, stacks, superficie, textos, textual, redact  # noqa: E402

VERSAO = 1
MAX_SIMBOLOS = 300      # teto para não varrer o repo inteiro por símbolo


def _dentro(caminho: str, area: str | None) -> bool:
    return area is None or caminho == area or caminho.startswith(f'{area}/')


def apurar(projeto: Path, area: str | None = None) -> dict:
    todos = mod_arvore.varrer(projeto)
    arquivos = [a for a in todos if _dentro(a['caminho'], area)]

    # stack e ambiente ACIMA da área entram herdados e marcados: sem isto o
    # "Como entrar" de uma área esvazia, porque o manifesto mora na raiz
    componentes = []
    for c in stacks.detectar(projeto):
        if _dentro(c['caminho'], area):
            componentes.append({**c, 'de_fora_da_area': False})
        elif area and (c['caminho'] in ('', '.') or area.startswith(f"{c['caminho']}/")):
            componentes.append({**c, 'de_fora_da_area': True})

    simbolos = textual.simbolos_de(arquivos)[:MAX_SIMBOLOS]
    # os símbolos são os da área, procurados no repositório INTEIRO: senão some
    # quem usa a área de fora
    por_simbolo = {s: m for s, m in textual.todas_as_mencoes(projeto, simbolos).items()
                   if len(m) > 1}             # 1 menção é a própria definição

    # Só as CHAVES do ambiente. Saber que o projeto usa `STRIPE_SECRET` orienta quem
    # chega; o valor nunca entra. Extrair a chave aqui — em vez de ler tudo e redigir
    # depois — é o que garante que não existe caminho pelo qual o valor chegue.
    ambiente = {}
    for item in todos:
        nome = Path(item['caminho']).name
        if nome != '.env' and not nome.startswith('.env.'):
            continue
        # o `.env` da RAIZ vale para qualquer área: é dele que sai o "como subir"
        if not (_dentro(item['caminho'], area) or Path(item['caminho']).parent == Path('.')):
            continue
        try:
            texto = (projeto / item['caminho']).read_text('utf-8', 'replace')
        except OSError:
            continue
        ambiente[item['caminho']] = redact.chaves_de_env(texto)

    return {
        'gerado_em_versao': VERSAO,
        # `caminhos_do_projeto` existe para a guarda de evidência: sem ele, uma
        # orientação citando `fora/b.py` — exatamente a frase que a seção existe
        # para dizer — era recusada, porque a árvore recortada não a contém.
        'caminhos_do_projeto': sorted(a['caminho'] for a in todos),
        'escopo': {'area': area, 'criterio': 'prefixo de caminho',
                   'n_arquivos': len(arquivos)},
        'stacks': componentes,
        'arvore': arquivos,
        'historia': historia.historico(projeto, area=area),
        # o retrato é do PROJETO, não da área: quantas pessoas conhecem este
        # código e há quanto tempo ninguém encosta nele não mudam com o recorte
        'retrato': historia.retrato(projeto),
        'imports': imports.grafo(projeto, componentes),
        'superficie': [s for s in superficie.detectar(projeto)
                       if _dentro(s['caminho'], area)],
        # `textos` NÃO é recortado: a guarda da vacuidade exige que `fonte` esteja
        # aqui, e recortar impediria o agente de citar `docs/arquitetura.md` numa
        # rodada de área. O conteúdo já passa por redação, então não há custo.
        'textos': textos.coletar(projeto, todos),
        'ambiente': dict(sorted(ambiente.items())),
        'mencoes': dict(sorted(por_simbolo.items())),
    }


def apurar_areas(projeto: Path) -> dict:
    """A fase barata: o que alimenta o menu de escopo. Não grava nada.

    Só `os.walk` com poda, mais uma consulta git limitada por data. É a lista
    branca da restrição: a única leitura de arquivo permitida aqui é a das fontes
    textuais, porque a conferência de trecho literal depende do conteúdo delas.
    """
    arquivos = mod_arvore.varrer(projeto)
    recentes = historia.commits_por_pasta(projeto)
    componentes = stacks.detectar(projeto)
    # as fontes textuais são lidas AQUI, na fase barata: a conferência de trecho
    # literal depende do conteúdo delas, e é a única leitura que a lista branca
    # da restrição permite nesta fase
    fontes = textos.coletar(projeto, arquivos)
    return {
        'areas': areas.detectar(arquivos, recentes or None, componentes),
        'total_arquivos': len(arquivos),
        'stacks': len(componentes),
        'fontes_textuais': sorted(fontes),
        'ordenado_por': 'commits_recentes' if recentes else 'arquivos',
    }


def main() -> int:
    p = argparse.ArgumentParser(description='Apura os fatos de um projeto.')
    p.add_argument('--projeto', required=True, help='raiz do projeto a ler')
    p.add_argument('--out', default=None, help='diretório onde gravar o inventário')
    p.add_argument('--areas', action='store_true',
                   help='imprime as áreas em stdout e sai, sem gravar nada')
    p.add_argument('--area', default=None,
                   help='recorta a varredura a esta área (o caminho, não o rótulo)')
    args = p.parse_args()

    projeto = Path(args.projeto).resolve()
    if not projeto.is_dir():
        print(f'não é um diretório: {projeto}', file=sys.stderr)
        return 2

    if args.areas:
        print(json.dumps(apurar_areas(projeto), indent=1, ensure_ascii=False))
        return 0

    if not args.out:
        print('--out é obrigatório fora do modo --areas', file=sys.stderr)
        return 2

    saida = Path(args.out).resolve()
    saida.mkdir(parents=True, exist_ok=True)

    inventario = apurar(projeto, area=args.area)
    # NÃO passe o JSON pronto por `redigir`: ele casa `chave: valor` linha a linha, e
    # linha de JSON é exatamente isso — `"AuthController": [` virava
    # `"AuthController": ***` e o arquivo saía inválido. A proteção acontece na
    # ORIGEM: o inventário carrega caminho, contagem e nome de chave. A exceção é
    # `textos`, que carrega CONTEÚDO porque a conferência de trecho literal depende
    # dele — e por isso ele passa por redação LINHA A LINHA antes de entrar, com teto
    # de 64 KB por arquivo e 384 KB na seção.
    texto = json.dumps(inventario, indent=1, ensure_ascii=False, sort_keys=True)
    (saida / 'inventory.json').write_text(texto + '\n', encoding='utf-8')

    print(f'{saida / "inventory.json"}')
    print(f'{len(inventario["arvore"])} arquivos · {len(inventario["stacks"])} stack(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
