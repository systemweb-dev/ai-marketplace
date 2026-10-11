"""O que mudou entre a rodada anterior e esta.

O documento inteiro é função pura das suas entradas e **regenera do zero** a cada
rodada. O preço disso era não dizer o que mudou: quem já tinha lido relia tudo para
descobrir que um arquivo entrou no mapa de perigo. Aqui o `inventory.prev.json` — o
inventário da rodada anterior, girado pelo `scan.py` — entra como terceira entrada, e
a pureza continua: mesmos três arquivos, mesmo documento.

**Medido antes de desenhado**, num projeto real com um mês de 63 commits entre as
duas rodadas. Três coisas a medição decidiu, e nenhuma delas era o que eu esperava:

1. **Número que se move em item que FICOU na lista é ruído.** Quatro arquivos
   perigosos tiveram `dependentes` subindo de 1 a 3 (`Helper.php` 59→62): nada que
   o leitor faça muda, porque o arquivo já estava na lista. Só entrada e saída saem.
2. **Reordenação do topo da co-mudança é ruído, e pior: é redundante.** Com teto
   de 10, três pares "novos no topo" — dois deles outro `Rotas.php + Middleware.php`,
   acoplamento que o documento já estampa na primeira linha. O que sai aqui é só o
   par que **entrou na lista**, que o teto de 40 pares já recortava.
3. **Lista cortada não autoriza dizer "novo" nem "acabou".** A co-mudança é cortada
   em 40 pares. Entrar na lista é fato — o par mudou junto o bastante para passar
   os outros. **Sair não é**: na rodada medida, três pares "saíram" com 3x e 4x,
   empurrados para fora do corte por pares que cresceram, e a linha dizia que um
   acoplamento tinha acabado quando ninguém tinha tocado nele. Em lista cortada só
   a entrada sai, e o documento diz que a saída não é apurada.

E uma trava que vale mais que as três: **comparar rodadas de recortes diferentes
inventa movimento**. Uma rodada `--area api` contra uma rodada do projeto inteiro
reportaria centenas de arquivos "saindo". A comparação é recusada inteira, com motivo
— porque aqui a invariante da skill tem a forma mais perigosa que ela assume: linha
de mudança errada manda alguém investigar o que não aconteceu.
"""
from pathlib import Path

# Quantos itens de cada grupo o documento mostra antes de resumir o resto. Cinco
# porque a medição real produziu no máximo três por grupo num mês inteiro: teto que
# nunca encosta em rodada normal, e que impede uma rodada anormal (o primeiro
# `git pull` de um ano de trabalho) de virar duas telas de lista.
TETO_POR_GRUPO = 5

ROTULOS = {
    'perigo': 'onde é perigoso mexer',
    'sem_alcance': 'nenhum import alcança',
    'co_mudanca': 'muda junto',
    'superficie': 'superfície pública',
    'ambiente': 'variáveis de ambiente',
    'servicos': 'serviços do compose',
    'comandos': 'scripts de subida',
}


def _dias(n: int) -> str:
    return f'parado há {n} {"dia" if n == 1 else "dias"}'


def frase_do_numero(item: dict) -> str:
    """O texto puro de um número que se moveu. Vive aqui, e não nos dois emissores,
    porque é a parte que não tem marcação: deixá-la duplicada é convidar os dois
    documentos a contarem a mesma mudança com dois números diferentes."""
    antes, depois = item['antes'], item['depois']
    chave = item['chave']
    if chave == 'commits':
        d = depois - antes
        # sem "desde a rodada anterior": o título da seção já diz isso, e repetir
        # gasta a linha mais importante da seção com a moldura dela
        return f'{d} commit{"" if d == 1 else "s"} novo{"" if d == 1 else "s"} ({antes} → {depois})'
    if chave == 'parado':
        if depois == 0 and antes > 0:
            return (f'voltou a andar: estava parado há {antes} '
                    f'{"semana" if antes == 1 else "semanas"}')
        if antes == 0 and depois > 0:
            return (f'parou: ninguém encosta há {depois} '
                    f'{"semana" if depois == 1 else "semanas"}')
        return (f'parado há {depois} {"semana" if depois == 1 else "semanas"}, '
                f'antes {antes}')
    if chave == 'arquivos':
        d = depois - antes
        sinal = '+' if d > 0 else ''
        return f'{sinal}{d} arquivos ({antes} → {depois})'
    if chave == 'linhas':
        d = depois - antes
        sinal = '+' if d > 0 else ''
        return f'{sinal}{d} linhas de texto ({antes} → {depois})'
    return f'{antes} → {depois}'      # chave nova sem frase: mostra os dois números


# ─────────────────────────── as extrações, uma por grupo ──────────────────────
# Cada uma devolve {identidade: {nomes, detalhe}}. A identidade é o que casa o item
# entre as duas rodadas e nunca vai à tela; `nomes` é o que o documento mostra em
# fonte de código, e `detalhe` é texto puro da rodada NOVA. Os dois são separados
# porque a primeira versão remontava os nomes partindo a identidade em ` + `, e um
# caminho que contivesse ` + ` sairia na tela como dois caminhos inexistentes.

def _perigo(inv: dict) -> dict:
    return {x['caminho']: {
        'nomes': [x['caminho']],
        'detalhe': f'{x["dependentes"]} dependentes, {x["mudancas"]} mudanças'}
        for x in (inv.get('julgamento') or {}).get('perigo') or []}


def _sem_alcance(inv: dict) -> dict:
    return {x['caminho']: {'nomes': [x['caminho']],
                           'detalhe': _dias(x['dias_parado'])}
            for x in (inv.get('julgamento') or {}).get('sem_alcance') or []}


def _co_mudanca(inv: dict) -> dict:
    # a identidade é o par; `arquivos` já vem ordenado pelo `history`, então o mesmo
    # par tem a mesma identidade nas duas rodadas
    return {tuple(x['arquivos']): {'nomes': list(x['arquivos']),
                                   'detalhe': f'{x["vezes"]}x'}
            for x in (inv.get('historia') or {}).get('co_mudanca') or []}


def _superficie(inv: dict) -> dict:
    return {x['caminho']: {'nomes': [x['caminho']], 'detalhe': x['tipo']}
            for x in inv.get('superficie') or []}


def _ambiente(inv: dict) -> dict:
    """A identidade é (variável, arquivo) para a mesma variável em dois `.env`
    contar duas vezes — são dois ambientes, e declarar num e não no outro é a
    diferença que faz alguém passar a tarde atrás de um erro de configuração."""
    fora = {}
    for arquivo, chaves in (inv.get('ambiente') or {}).items():
        for chave in chaves:
            fora[(chave, arquivo)] = {'nomes': [chave], 'detalhe': f'em {arquivo}'}
    return fora


def _servicos(inv: dict) -> dict:
    fora = {}
    for c in (inv.get('execucao') or {}).get('composicoes') or []:
        for servico in c.get('servicos') or []:
            fora[servico['nome']] = {'nomes': [servico['nome']],
                                     'detalhe': f'em {c["caminho"]}'}
    return fora


def _comandos(inv: dict) -> dict:
    fora = {}
    for c in (inv.get('execucao') or {}).get('comandos') or []:
        for script in c.get('candidatos') or []:
            fora[script] = {'nomes': [script], 'detalhe': f'em {c["caminho"]}'}
    return fora


# ───────────────── o que cada grupo exige da rodada ANTERIOR ──────────────────
# Lista vazia na rodada anterior tem duas causas opostas — mediu e não achou, ou
# não pôde medir — e tratar a segunda como "não havia nada" faz o documento
# anunciar oito arquivos perigosos novos quando o que entrou foi a medição. O
# pré-requisito é o que separa as duas, e quem não o cumpre vira "não comparado".

def _tem_git(inv: dict) -> bool:
    return bool(inv.get('mudanca_por_arquivo'))


def _tem_import(inv: dict) -> bool:
    return bool((inv.get('imports') or {}).get('arestas'))


def _tem_co_mudanca(inv: dict) -> bool:
    return bool((inv.get('historia') or {}).get('co_mudanca'))


def _sempre(inv: dict) -> bool:
    return True


# `cortada` diz que a lista de origem tem teto, e com ela SÓ A ENTRADA é fato: quem
# some de uma lista de 40 pode ter sido empurrado para fora por quem cresceu. `perigo`
# e `sem_alcance` não têm teto — entram por limiar —, então sair delas é fato: o
# arquivo ganhou teste, perdeu dependentes ou voltou a ser tocado.
GRUPOS = (
    # chave,        extrator,  pré-requisito na rodada anterior,  motivo,  cortada
    ('perigo', _perigo, lambda i: _tem_git(i) and _tem_import(i),
     'a rodada anterior não tinha grafo de import ou histórico para medir perigo',
     False),
    ('sem_alcance', _sem_alcance, lambda i: _tem_git(i) and _tem_import(i),
     'a rodada anterior não tinha grafo de import ou histórico', False),
    ('co_mudanca', _co_mudanca, _tem_co_mudanca,
     'a rodada anterior não apurou co-mudança', True),
    ('superficie', _superficie, _sempre, '', False),
    ('ambiente', _ambiente, _sempre, '', False),
    ('servicos', _servicos, _sempre, '', True),
    ('comandos', _comandos, _sempre, '', False),
)

# O que o documento diz quando a saída não é apurada. Fica aqui, com a lista que o
# causa, para o leitor saber que o silêncio é teto e não ausência.
CORTES = {
    'co_mudanca': 'a lista carrega os 40 pares mais fortes',
    'servicos': 'a lista carrega os primeiros serviços do arquivo',
}

NUMEROS = (
    # chave,     onde está,                        posição no documento
    ('commits', ('retrato', 'commits'), 'abertura'),
    ('parado', ('retrato', 'semanas_parado'), 'abertura'),
    ('arquivos', None, 'fecho'),        # contado da árvore
    ('linhas', None, 'fecho'),          # somado de `linhas_por_arquivo`
)


def _numero(inv: dict, chave: str, caminho) -> int | None:
    if chave == 'arquivos':
        return len(inv.get('arvore') or [])
    if chave == 'linhas':
        valores = (inv.get('linhas_por_arquivo') or {}).values()
        return sum(valores) if valores else None
    secao, campo = caminho
    alvo = inv.get(secao) or {}
    return alvo.get(campo)


def _recusa(novo: dict, velho: dict) -> str | None:
    """Por que esta comparação não pode ser feita. Recusar inteiro é a decisão
    certa quando as duas rodadas não olham a mesma coisa: linha de mudança errada
    manda alguém procurar o que não aconteceu, e não deixa rastro."""
    if novo.get('gerado_em_versao') != velho.get('gerado_em_versao'):
        return (f'o inventário anterior foi gerado na versão '
                f'{velho.get("gerado_em_versao")} e este na '
                f'{novo.get("gerado_em_versao")} — os campos podem ter mudado de forma')
    a, b = novo.get('escopo') or {}, velho.get('escopo') or {}
    atual = (a.get('tipo'), a.get('area'), a.get('funcionalidade'))
    anterior = (b.get('tipo'), b.get('area'), b.get('funcionalidade'))
    if atual != anterior:
        def diz(e):
            return (f'a área `{e[1]}`' if e[0] == 'area' else
                    f'a funcionalidade `{e[2]}`' if e[0] == 'funcionalidade' else
                    'o projeto inteiro')
        return (f'a rodada anterior cobriu {diz(anterior)} e esta cobre '
                f'{diz(atual)} — recortes diferentes não se comparam')
    if novo.get('projeto') and velho.get('projeto') \
            and novo['projeto'] != velho['projeto']:
        return (f'o inventário anterior é de `{velho["projeto"]}` e este é de '
                f'`{novo["projeto"]}`')
    return None


def comparar(novo: dict, velho: dict | None) -> dict:
    """O que mudou. Sem rodada anterior, devolve a estrutura vazia — e o documento
    diz que esta é a primeira, que é fato, não lacuna."""
    fora = {'houve_rodada_anterior': velho is not None, 'lacuna': None,
            'nao_comparado': [], 'numeros': [], 'listas': [], 'nada_mudou': False}
    if velho is None:
        return fora

    if motivo := _recusa(novo, velho):
        fora['lacuna'] = motivo
        return fora

    for chave, extrair, pre_requisito, motivo, cortada in GRUPOS:
        if not pre_requisito(velho):
            fora['nao_comparado'].append({'chave': chave, 'motivo': motivo})
            continue
        agora, antes = extrair(novo), extrair(velho)
        entrou = sorted(set(agora) - set(antes))
        saiu = [] if cortada else sorted(set(antes) - set(agora))
        if not entrou and not saiu:
            continue
        fora['listas'].append({
            'chave': chave,
            'entrou': [agora[k] for k in entrou[:TETO_POR_GRUPO]],
            'saiu': [antes[k] for k in saiu[:TETO_POR_GRUPO]],
            'entrou_omitidos': max(0, len(entrou) - TETO_POR_GRUPO),
            'saiu_omitidos': max(0, len(saiu) - TETO_POR_GRUPO),
            'saida_nao_apurada': CORTES[chave] if cortada else None,
        })

    for chave, caminho, posicao in NUMEROS:
        antes, depois = _numero(velho, chave, caminho), _numero(novo, chave, caminho)
        # `None` é não apurado, e 0 em cima de None seria o zero no lugar do "não
        # sei" que esta skill não emite
        if antes is None or depois is None or antes == depois:
            continue
        if chave in ('commits', 'parado') and not _tem_git(velho):
            fora['nao_comparado'].append(
                {'chave': chave, 'motivo': 'a rodada anterior não tinha histórico git'})
            continue
        fora['numeros'].append({'chave': chave, 'antes': antes, 'depois': depois,
                                'posicao': posicao})

    fora['nada_mudou'] = not (fora['numeros'] or fora['listas'])
    return fora


def ler_anterior(base) -> dict | None:
    """O inventário da rodada anterior, se o `scan.py` girou um. Inválido é tratado
    como ausente: a seção some, e é melhor do que o emissor morrer por causa de um
    arquivo de apoio que ninguém edita à mão."""
    import json
    arquivo = Path(base) / 'inventory.prev.json'
    if not arquivo.exists():
        return None
    try:
        dados = json.loads(arquivo.read_text('utf-8'))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None
