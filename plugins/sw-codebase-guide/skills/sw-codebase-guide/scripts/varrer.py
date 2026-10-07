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
from lib import historia, imports, stacks, superficie, textual, redact  # noqa: E402

VERSAO = 1
MAX_SIMBOLOS = 300      # teto para não varrer o repo inteiro por símbolo


def apurar(projeto: Path) -> dict:
    componentes = stacks.detectar(projeto)
    arquivos = mod_arvore.varrer(projeto)

    simbolos = textual.simbolos_de(arquivos)[:MAX_SIMBOLOS]
    # uma passada só pelos arquivos, casando todos os símbolos
    por_simbolo = {s: m for s, m in textual.todas_as_mencoes(projeto, simbolos).items()
                   if len(m) > 1}             # 1 menção é a própria definição

    # Só as CHAVES do ambiente. Saber que o projeto usa `STRIPE_SECRET` orienta quem
    # chega; o valor nunca entra. Extrair a chave aqui — em vez de ler tudo e redigir
    # depois — é o que garante que não existe caminho pelo qual o valor chegue.
    ambiente = {}
    for item in arquivos:
        nome = Path(item['caminho']).name
        if nome == '.env' or nome.startswith('.env.'):
            try:
                texto = (projeto / item['caminho']).read_text('utf-8', 'replace')
            except OSError:
                continue
            ambiente[item['caminho']] = redact.chaves_de_env(texto)

    return {
        'gerado_em_versao': VERSAO,
        'stacks': componentes,
        'arvore': arquivos,
        'historia': historia.historico(projeto),
        'imports': imports.grafo(projeto, componentes),
        'superficie': superficie.detectar(projeto),
        'ambiente': dict(sorted(ambiente.items())),
        'mencoes': dict(sorted(por_simbolo.items())),
    }


def main() -> int:
    p = argparse.ArgumentParser(description='Apura os fatos de um projeto.')
    p.add_argument('--projeto', required=True, help='raiz do projeto a ler')
    p.add_argument('--out', required=True, help='diretório onde gravar o inventário')
    args = p.parse_args()

    projeto = Path(args.projeto).resolve()
    if not projeto.is_dir():
        print(f'não é um diretório: {projeto}', file=sys.stderr)
        return 2

    saida = Path(args.out).resolve()
    saida.mkdir(parents=True, exist_ok=True)

    inventario = apurar(projeto)
    # NÃO passe o JSON pronto por `redigir`: ele casa `chave: valor` linha a linha, e
    # linha de JSON é exatamente isso — `"AuthController": [` virava
    # `"AuthController": ***` e o arquivo saía inválido. A proteção acontece na
    # ORIGEM: o inventário só carrega caminho, contagem e nome de chave, nunca conteúdo.
    texto = json.dumps(inventario, indent=1, ensure_ascii=False, sort_keys=True)
    (saida / 'inventory.json').write_text(texto + '\n', encoding='utf-8')

    print(f'{saida / "inventory.json"}')
    print(f'{len(inventario["arvore"])} arquivos · {len(inventario["stacks"])} stack(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
