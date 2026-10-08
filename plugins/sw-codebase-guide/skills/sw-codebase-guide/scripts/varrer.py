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
from lib import (areas, funcionalidades, historia, imports, julgar,  # noqa: E402
                 recorte as mod_recorte, stacks, superficie, textos,
                 textual, redact)

VERSAO = 1
MAX_SIMBOLOS = 300      # teto para não varrer o repo inteiro por símbolo


def _governa(caminho_do_componente: str, arquivos: list) -> bool:
    """O manifesto está fora do recorte, mas manda nos arquivos que estão?

    Com `--area` isso era `area.startswith(componente + '/')`, que só funciona
    porque área é um prefixo. Uma funcionalidade é um conjunto espalhado — o
    cadastro mora em duas aplicações —, e a pergunta certa é a mesma para os
    dois casos: algum arquivo do recorte está debaixo deste componente?
    """
    if caminho_do_componente in ('', '.'):
        return True
    prefixo = f'{caminho_do_componente}/'
    return any(a['caminho'].startswith(prefixo) for a in arquivos)


def apurar(projeto: Path, recorte=None) -> dict:
    recorte = recorte or mod_recorte.tudo()
    todos = mod_arvore.varrer(projeto)
    arquivos = [a for a in todos if a['caminho'] in recorte]

    # stack e ambiente ACIMA do recorte entram herdados e marcados: sem isto o
    # "Como entrar" esvazia, porque o manifesto mora na raiz
    componentes = []
    for c in stacks.detectar(projeto):
        if c['caminho'] in recorte:
            componentes.append({**c, 'de_fora_da_area': False})
        elif recorte.parcial and _governa(c['caminho'], arquivos):
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
        if not (item['caminho'] in recorte or Path(item['caminho']).parent == Path('.')):
            continue
        try:
            texto = (projeto / item['caminho']).read_text('utf-8', 'replace')
        except OSError:
            continue
        ambiente[item['caminho']] = redact.chaves_de_env(texto)

    inventario = {
        'gerado_em_versao': VERSAO,
        # `caminhos_do_projeto` existe para a guarda de evidência: sem ele, uma
        # orientação citando `fora/b.py` — exatamente a frase que a seção existe
        # para dizer — era recusada, porque a árvore recortada não a contém.
        'caminhos_do_projeto': sorted(a['caminho'] for a in todos),
        'escopo': recorte.como_escopo(len(arquivos)),
        'stacks': componentes,
        'arvore': arquivos,
        'historia': historia.historico(projeto, recorte=recorte),
        # o retrato é do PROJETO, não da área: quantas pessoas conhecem este
        # código e há quanto tempo ninguém encosta nele não mudam com o recorte
        'retrato': historia.retrato(projeto),
        'imports': imports.grafo(projeto, componentes, todos, recorte=recorte),
        'superficie': [s for s in superficie.detectar(projeto)
                       if s['caminho'] in recorte],
        # `textos` NÃO é recortado: a guarda da vacuidade exige que `fonte` esteja
        # aqui, e recortar impediria o agente de citar `docs/arquitetura.md` numa
        # rodada de área. O conteúdo já passa por redação, então não há custo.
        'textos': textos.coletar(projeto, todos),
        'ambiente': dict(sorted(ambiente.items())),
        'mencoes': dict(sorted(por_simbolo.items())),
    }
    # O julgamento vem por último porque LÊ o resto: ele não apura nada por conta
    # própria, só recorta o que já está medido e aplica limiares declarados. Fica no
    # inventário, e não no `montar.py`, para o documento continuar sendo função pura
    # dos dois arquivos — e para o número poder ser conferido sem rodar o emissor.
    por_arquivo = historia.por_arquivo(projeto)
    inventario['julgamento'] = {
        'perigo': julgar.onde_e_perigoso(inventario, por_arquivo),
        'sem_alcance': julgar.sem_alcance(
            inventario, {c: v['ultima'] for c, v in por_arquivo.items()}),
        'risco': julgar.risco_visivel(inventario, historia.rastreados(projeto)),
        'dossie': julgar.dossie_de_decisao(inventario),
    }
    # a data da última mudança de cada arquivo fica no inventário porque é ela que
    # envelhece uma resposta humana: respondido em outubro, arquivo mexido em
    # dezembro, a pergunta pode ter voltado a valer
    inventario['mudanca_por_arquivo'] = {
        c: v['ultima'] for c, v in sorted(por_arquivo.items())}
    return inventario


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


def apurar_funcionalidades(projeto: Path) -> dict:
    """A outra fase barata: o menu do *o quê*, irmão do `apurar_areas`.

    O `--areas` responde onde mexer; este responde o que entender. Quem recebe
    um projeto não pergunta por `src/app/(app)`, pergunta pelo cadastro.
    """
    arquivos = mod_arvore.varrer(projeto)
    achados = funcionalidades.candidatos(arquivos)
    return {
        'funcionalidades': achados,
        'total_arquivos': len(arquivos),
        'criterio': (f'nome que aparece em {funcionalidades.MIN_PAPEIS} ou mais '
                     f'papéis diferentes (teste e barril não contam)'),
    }


def main() -> int:
    p = argparse.ArgumentParser(description='Apura os fatos de um projeto.')
    p.add_argument('--projeto', required=True, help='raiz do projeto a ler')
    p.add_argument('--out', default=None, help='diretório onde gravar o inventário')
    p.add_argument('--areas', action='store_true',
                   help='imprime as áreas em stdout e sai, sem gravar nada')
    p.add_argument('--area', default=None,
                   help='recorta a varredura a esta área (o caminho, não o rótulo)')
    p.add_argument('--funcionalidades', action='store_true',
                   help='imprime as funcionalidades candidatas e sai, sem gravar')
    p.add_argument('--funcionalidade', default=None,
                   help='recorta a varredura a esta funcionalidade (o termo)')
    args = p.parse_args()

    projeto = Path(args.projeto).resolve()
    if not projeto.is_dir():
        print(f'não é um diretório: {projeto}', file=sys.stderr)
        return 2

    if args.areas:
        print(json.dumps(apurar_areas(projeto), indent=1, ensure_ascii=False))
        return 0

    if args.funcionalidades:
        print(json.dumps(apurar_funcionalidades(projeto), indent=1, ensure_ascii=False))
        return 0

    if args.area and args.funcionalidade:
        print('--area e --funcionalidade são dois recortes; escolha um',
              file=sys.stderr)
        return 2

    if not args.out:
        print('--out é obrigatório fora do modo --areas', file=sys.stderr)
        return 2

    saida = Path(args.out).resolve()
    saida.mkdir(parents=True, exist_ok=True)

    if args.funcionalidade:
        termo = ' '.join(funcionalidades.palavras(args.funcionalidade))
        todos = mod_arvore.varrer(projeto)
        componentes = stacks.detectar(projeto)
        arestas = imports.grafo(projeto, componentes, todos)['arestas']
        fatia = funcionalidades.recortar(todos, arestas, termo)
        if not fatia['nucleo']:
            print(f'nenhum arquivo casa com {termo!r} — rode --funcionalidades '
                  f'para ver os termos que este projeto usa', file=sys.stderr)
            return 2
        recorte = mod_recorte.por_funcionalidade(fatia)
    elif args.area:
        recorte = mod_recorte.por_area(args.area)
    else:
        recorte = mod_recorte.tudo()

    inventario = apurar(projeto, recorte=recorte)
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
