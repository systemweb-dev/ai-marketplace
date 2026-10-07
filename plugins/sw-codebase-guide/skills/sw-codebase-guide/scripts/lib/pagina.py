"""Os blocos do documento humano, e o HTML deles.

É um EMISSOR, irmão do `montar.py`: as duas saídas vêm do mesmo `inventory.json`
e da mesma `interpretation.toml`, e nenhuma delas é conversão da outra. O HTML
não nasce do Markdown de propósito — hierarquia de três níveis, barras, cartões e
etiqueta de confiança não cabem em Markdown, e converter perderia exatamente o que
faz o documento ser lido em vez de folheado.

**O desenho foi decidido vendo, não descrevendo** (mockup aprovado em 07/10), e
cada peça resolve um problema de leitura medido ali:

- **três níveis de bloco** (`n1` espinha · `n2` decide · `n3` apoio) — antes todo
  bloco era uma caixa igual com um título minúsculo em cinza, e o olho não tinha
  onde pousar primeiro;
- **uma pergunta sob cada título** — o rótulo nomeia, a pergunta orienta. "Quem
  mais depende disto" vira útil quando vem seguido de *o que quebra se você mudar
  uma coluna*;
- **legenda dos níveis de confiança** — a etiqueta era a coisa menor da página,
  sendo o dispositivo mais importante dela;
- **mapa de leitura por intenção**, não sumário — *vai mexer? vai estimar? vai
  conversar com quem conhece?*

Nenhum valor de segredo passa por aqui: o inventário já carrega só as CHAVES do
ambiente, extraídas na origem.
"""
import html as _html
import re

from lib.arvore import ATIVOS, NAO_E_CODIGO, eh_codigo  # noqa: F401
from collections import Counter
from pathlib import Path

NIVEIS = {
    'fato': 'medido',
    'declarado': 'citado',
    'deducao': 'deduzido',
    'lacuna': 'não apurado',
}

# extensão que não é código: contá-las junto fazia "2.036 arquivos" se ler como
# dois mil arquivos de código, num projeto em que metade eram PNG e SVG


def e(t) -> str:
    """Escapa para HTML. Tudo que vem do projeto lido passa por aqui."""
    return _html.escape(str(t), quote=True)


def citacao(t) -> str:
    """Escapa e DEPOIS renderiza o negrito e o código do Markdown.

    O trecho literal vem de um `.md`, então `**single-tenant**` chegava cru à
    tela. Escapar primeiro é o que impede HTML da fonte virar HTML da página;
    renderizar depois é o que faz a citação se parecer com o que está escrito lá.
    """
    t = e(t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', t)


def _tag(nivel: str) -> str:
    return f'<span class="tag" data-n="{nivel}">{NIVEIS.get(nivel, nivel)}</span>'


def _bloco(titulo, nivel_conf, pergunta, corpo, classe='n2', largo=False, rodape=''):
    largura = ' largo' if largo else ''
    etiqueta = f' {_tag(nivel_conf)}' if nivel_conf else ''
    sub = f'<p class="sub">{pergunta}</p>' if pergunta else ''
    pe = f'<p class="leg">{rodape}</p>' if rodape else ''
    return (f'<section class="bloco{largura} {classe}">'
            f'<h2>{titulo}{etiqueta}</h2>{sub}{corpo}{pe}</section>')


def _barras(itens, unidade=''):
    """Lista de (rótulo, valor), proporcional ao maior."""
    if not itens:
        return ''
    maior = max(v for _, v in itens) or 1
    linhas = ''.join(
        f'<li><span>{e(r)}</span><i style="--p:{round(v * 100 / maior)}"></i>'
        f'<b>{e(v)}{unidade}</b></li>' for r, v in itens)
    return f'<ul class="barras">{linhas}</ul>'


def _eh_teste(caminho: str) -> bool:
    c = caminho.lower()
    return ('test' in c or 'spec' in c or '__tests__' in c) and 'contest' not in c


# ───────────────────────────── os blocos ─────────────────────────────

def bloco_retrato(inv: dict) -> str:
    r = inv.get('retrato') or {}
    arvore = inv.get('arvore') or []
    # A condição olha para a MEDIDA, não para a existência de lacuna: num monorepo o
    # retrato tem números e uma lacuna, que ali não é ausência e sim procedência — "a
    # soma de 4 sub-repositórios". Carimbar NÃO APURADO sobre seis autores e 782
    # commits medidos é o mesmo erro de sinal, na direção contrária.
    if r.get('autores') is None:
        # NUNCA zero no lugar de "não sei": `0 autores` se lê como "ninguém mexe
        # nisso", e `1` se lê como "uma pessoa só" — a diferença é todo o valor
        motivo = r.get('lacuna') or 'sem histórico'
        corpo = f'<p class="aviso">Não apurado: {e(motivo)}.</p>'
        return _bloco('Retrato do projeto', 'lacuna',
                      'Se vale pegar este projeto, e com quanto cuidado.',
                      corpo, classe='n1 retrato', largo=True,
                      rodape='Sem o histórico, o fator ônibus e a idade do código '
                             'ficam sem resposta. É pergunta para quem entregou o projeto.')

    # o retrato é do PROJETO, não da área — autores e commits já eram. O
    # percentual saía da árvore RECORTADA, e uma área sem teste virava
    # "0% é teste · mexer aqui não tem rede" num projeto com 44% de cobertura.
    universo = inv.get('caminhos_do_projeto') or [a['caminho'] for a in arvore]
    testes = sum(1 for c in universo if _eh_teste(c))
    pct = round(testes * 100 / len(universo)) if universo else 0
    cartoes = [
        (r['autores'], 'pessoa commitou' if r['autores'] == 1 else 'pessoas commitaram',
         f'{r["commits"]} commits. ' + (
             'Quem conhece este código é uma pessoa só: se ela não estiver '
             'disponível, não há segunda fonte.' if r['autores'] == 1 else
             'Há mais de uma fonte sobre como o código funciona.'), False),
        (f'{pct}%', 'é teste',
         f'{testes} dos {len(universo)} arquivos do projeto. ' + (
             'É um projeto com rede de segurança: mexer nele é menos arriscado do '
             'que o tamanho sugere.' if pct >= 20 else
             'Mexer aqui não tem rede: a verificação é manual.'), pct < 20),
        (r['semanas_de_vida'], 'semanas de vida',
         f'Primeiro commit em {_data(r["primeiro_commit"])}, último em '
         f'{_data(r["ultimo_commit"])}.', False),
        (r['semanas_parado'], 'semanas parado',
         'Nenhum arquivo foi tocado desde então. Pode ser entrega concluída ou '
         'abandono: o código não distingue os dois.' if r['semanas_parado'] >= 3 else
         'Está sendo mexido agora.', r['semanas_parado'] >= 3),
    ]
    cartoes_html = ''.join(
        f'<div class="r{" alerta" if alerta else ""}"><b>{e(n)}</b>'
        f'<span>{e(rotulo)}</span><p>{e(texto)}</p></div>'
        for n, rotulo, texto, alerta in cartoes)
    return _bloco('Retrato do projeto', 'fato',
                  'Se vale pegar este projeto, e com quanto cuidado. Quatro números.',
                  f'<div class="retratos">{cartoes_html}</div>',
                  classe='n1 retrato', largo=True,
                  rodape=(f'De onde vêm estes números: {e(r["lacuna"])}.'
                          if r.get('lacuna') else ''))


def _data(iso: str) -> str:
    return f'{iso[8:10]}/{iso[5:7]}/{iso[:4]}' if iso and len(iso) >= 10 else '?'


def bloco_onde_mora(inv: dict) -> str:
    por_pasta = Counter()
    for a in inv.get('arvore') or []:
        partes = a['caminho'].split('/')
        por_pasta['/'.join(partes[:2]) if len(partes) > 2 else partes[0]] += 1
    itens = por_pasta.most_common(8)
    if not itens:
        return ''
    return _bloco('Onde o código mora', 'fato', 'Em que pastas o trabalho acontece.',
                  _barras(itens))


def bloco_do_que_e_feito(inv: dict) -> str:
    por_lingua = Counter(a['linguagem'] for a in (inv.get('arvore') or [])
                         if a['linguagem'] not in ATIVOS and not a['gerado'])
    itens = por_lingua.most_common(6)
    if not itens:
        return ''
    return _bloco('Do que é feito', 'fato', 'Em que linguagens o trabalho está escrito.',
                  _barras(itens), classe='n3')


def bloco_arquivos_maiores(inv: dict) -> str:
    # `gerado` fora: `package-lock.json` e `tsconfig.tsbuildinfo` apareciam no topo
    # da lista, e "onde está a massa do código" passava a responder outra pergunta
    maiores = sorted((a for a in (inv.get('arvore') or [])
                      if a['linguagem'] not in ATIVOS
                      and a['linguagem'] not in NAO_E_CODIGO
                      and not a['gerado']),
                     key=lambda a: -a['bytes'])[:5]
    if not maiores:
        return ''
    itens = [(_encurtar(a['caminho']), round(a['bytes'] / 1024)) for a in maiores]
    return _bloco('Arquivos maiores', 'fato', 'Onde está a massa do código.',
                  _barras(itens, ' KB'), classe='n3')


def _encurtar(caminho: str, teto: int = 32) -> str:
    """Encurta pela PASTA, nunca no meio do nome do arquivo.

    Cortar por caractere produzia `…afbad8760d14-179103…` e
    `…e/migrations/0001_core_tables.sql`: o leitor perde a única parte que
    identifica o arquivo. O nome final é o que importa; o caminho até ele é
    contexto, e é ele que cede.
    """
    if len(caminho) <= teto:
        return caminho
    partes = caminho.split('/')
    nome = partes[-1]
    if len(nome) >= teto:
        return '…/' + nome
    sobra = teto - len(nome) - 2
    prefixo = ''
    for parte in partes[:-1]:
        if len(prefixo) + len(parte) + 1 > sobra:
            break
        prefixo += parte + '/'
    return f'{prefixo}…/{nome}' if prefixo else f'…/{nome}' 


def bloco_ambiente(inv: dict) -> str:
    ambiente = inv.get('ambiente') or {}
    if not ambiente:
        return ''
    partes = []
    for arquivo, chaves in ambiente.items():
        nomes = ''.join(f'<code>{e(c)}</code>' for c in chaves)
        partes.append(f'<p class="leg"><code>{e(arquivo)}</code> declara '
                      f'{len(chaves)} variáveis</p><div class="chaves">{nomes}</div>')
    return _bloco('Variáveis que o ambiente precisa', 'fato',
                  'O que você precisa ter em mãos antes de subir.',
                  ''.join(partes), largo=True,
                  rodape='<b>Só os nomes.</b> O valor nunca é lido para dentro do '
                         'inventário, então não existe caminho pelo qual ele chegue aqui.')


def bloco_muda_junto(inv: dict) -> str:
    h = inv.get('historia') or {}
    area = (inv.get('escopo') or {}).get('area')
    if not h.get('co_mudanca'):
        motivo = h.get('lacuna') or 'não há pares suficientes para formar sinal'
        return _bloco('O que muda junto', 'lacuna',
                      'Quais arquivos exigem ser mexidos em par.',
                      f'<p class="aviso">Não apurado: {e(motivo)}.</p>', largo=True)
    linhas = []
    for c in h['co_mudanca'][:14]:
        marcados = []
        for caminho in c['arquivos']:
            fora = area and not (caminho == area or caminho.startswith(f'{area}/'))
            marcados.append(f'<code>{e(_encurtar(caminho, 40))}</code>'
                            + ('<em>fora</em>' if fora else ''))
        linhas.append(f'<li><b>{c["vezes"]}×</b>{marcados[0]} e {marcados[1]}</li>')
    de_onde = ' do projeto todo' if area else ''
    rodape = (f'De {h.get("commits", 0)} commits{de_onde}. '
              + ('A ponta marcada <em>fora</em> está fora do recorte: é ela que diz '
                 '"para mexer nesta área você mexe lá fora".' if area else
                 'Página costuma andar com o seu componente.'))
    return _bloco('O que muda junto', 'fato',
                  'Quais arquivos exigem ser mexidos em par, segundo o histórico.',
                  f'<ul class="duplas">{"".join(linhas)}</ul>', largo=True, rodape=rodape)


def bloco_superficie(inv: dict) -> str:
    sup = inv.get('superficie') or []
    if not sup:
        return ''
    por_tipo = Counter(s['tipo'] for s in sup)
    partes = []
    for tipo, n in por_tipo.most_common():
        exemplos = [x for x in sup if x['tipo'] == tipo][:3]
        amostra = ' · '.join(f'<code>{e(_encurtar(x["caminho"], 34))}</code>'
                             for x in exemplos)
        resto = f' <em>e mais {n - len(exemplos)}</em>' if n > len(exemplos) else ''
        partes.append(f'<dt>{e(n)} {e(tipo)}</dt><dd>{amostra}{resto}</dd>')
    itens = ''.join(partes)
    return _bloco('Superfície pública', 'deducao', 'Por onde o mundo de fora entra.',
                  f'<dl class="superficie">{itens}</dl>',
                  rodape='Reconhecida por <b>convenção de caminho</b>: é indício, não '
                         'prova. O que a convenção não nomeia não aparece aqui.')


def bloco_afirmacoes(afirmacoes: list, secao: str, titulo: str, pergunta: str,
                     classe='n1', nivel_bloco='declarado') -> str:
    delas = [a for a in afirmacoes if a.get('secao') == secao and a.get('nivel') != 'lacuna']
    if not delas:
        return ''
    itens = []
    for a in delas:
        fontes = ''.join(f'<em>{e(ev)}</em>' for ev in (a.get('evidencia') or []))
        itens.append(f'<li>{_tag(a.get("nivel", "deducao"))} {citacao(a["texto"])}{fontes}</li>')
    return _bloco(titulo, nivel_bloco, pergunta,
                  f'<ul class="regras">{"".join(itens)}</ul>', classe=classe, largo=True)


def bloco_lacunas(afirmacoes: list) -> str:
    lacunas = [a for a in afirmacoes if a.get('nivel') == 'lacuna']
    corpo = ''.join(
        f'<li><b>{citacao(a["texto"])}</b> — <em>{citacao(a.get("motivo", ""))}</em></li>'
        for a in lacunas) or '<li>Nenhuma lacuna foi registrada na interpretação.</li>'
    return _bloco('O que ficou sem resposta', 'lacuna',
                  'O que o código não respondeu. É a pauta da conversa com quem '
                  'conhece o sistema.',
                  f'<ul class="abertas">{corpo}</ul>',
                  classe='n1 lacuna', largo=True)


# ───────────────── as quatro partes da narrativa, em HTML ─────────────────
#
# O `leia-me.md` existe para versionar e dar diff; quem vai LER de ponta a ponta
# abre isto. Mesma fonte, mesmas guardas — só a vestimenta muda.

def _por_parte(narrativa: list, parte: str) -> list:
    return sorted((b for b in narrativa if b.get('parte') == parte),
                  key=lambda b: b.get('ordem', 0))


def bloco_o_que_e(narrativa: list) -> str:
    blocos = _por_parte(narrativa, 'o-que-e')
    if not blocos:
        return ''
    partes = []
    for b in blocos:
        # o literal ao lado da paráfrase: é assim que o leitor confere, e é a
        # única coisa que impede prosa fluente, verdadeira e vazia. Só o primeiro
        # bloco precisa citar — os seguintes podem vir de evidência convergente de
        # código, e aí não há literal nenhum para pôr aqui.
        partes.append(f'<p>{citacao(b["texto"])}</p>')
        if b.get('trecho'):
            partes.append(f'<blockquote>{citacao(b["trecho"])}'
                          f'<cite>{e(b.get("fonte", ""))}</cite></blockquote>')
    return _bloco('O que o produto faz', 'declarado',
                  'O que está escrito por quem construiu, com a citação ao lado.',
                  ''.join(partes), classe='n1', largo=True)


def bloco_percurso(narrativa: list) -> str:
    blocos = _por_parte(narrativa, 'percurso')
    if not blocos:
        return ''
    partes = []
    for b in blocos:
        partes.append(f'<p>{citacao(b["texto"])}</p>')
        saltos = b.get('saltos') or []
        if saltos:
            # o salto aparece ONDE acontece, não numa nota de rodapé: salto
            # escondido é o erro mais caro que este documento pode cometer
            itens = ''.join(f'<li>{citacao(s)}</li>' for s in saltos)
            partes.append(f'<ul class="saltos">{itens}</ul>')
    # "sem buraco" é afirmação sobre a JORNADA, não sobre o parágrafo: saía sob cada
    # bloco, e num percurso de três a página negava buraco duas vezes antes de
    # mostrar dois.
    if not any(b.get('saltos') for b in blocos):
        partes.append('<p class="leg"><b>Sem saltos:</b> o percurso foi seguido '
                      'do começo ao fim, sem buraco.</p>')
    return _bloco('O percurso de uma funcionalidade', 'deducao',
                  'O que acontece de ponta a ponta, e onde a leitura parou.',
                  ''.join(partes), classe='n1', largo=True)


def bloco_mapa(narrativa: list) -> str:
    blocos = _por_parte(narrativa, 'mapa')
    if not blocos:
        return ''
    return _bloco('Onde ficam as coisas', 'deducao',
                  'Em que pasta procurar o que você veio mexer.',
                  ''.join(f'<p>{citacao(b["texto"])}</p>' for b in blocos),
                  classe='n2', largo=True)


def bloco_orientacoes(narrativa: list) -> str:
    blocos = _por_parte(narrativa, 'orientacoes')
    if not blocos:
        return ''
    return _bloco('Para mexer', 'deducao',
                  'O que saber antes de abrir o editor.',
                  ''.join(f'<p>{citacao(b["texto"])}</p>' for b in blocos),
                  classe='n1', largo=True)


def bloco_resolucao(inv: dict) -> str:
    """Quanto do grafo foi de fato medido, em números absolutos.

    O percentual sozinho esconde a decisão que o produz: é o resolvedor que decide
    o que é `externo`, e inflar aquele balde infla a fração. Num projeto medido a
    diferença entre duas rotulagens plausíveis era 85,5% e 75,7% — o veredito sairia
    da rotulagem, não do resolvedor.
    """
    resolucao = (inv.get('imports') or {}).get('resolucao') or {}
    if not resolucao:
        return ''
    linhas = []
    for linguagem, c in sorted(resolucao.items()):
        resolvidos = (c['relativos'] + c['sufixo_unico'] + c['base_provada']
                      + c['config_conferida'])
        denominador = (resolvidos + c['ambiguos'] + c['pendurados']
                       + c['nao_resolvidos'])
        quanto = (f'{round(resolvidos * 100 / denominador)}%' if denominador
                  else '—')
        detalhe = (f'{resolvidos} de {denominador} imports internos. '
                   f'{c["externos"]} externos, {c["ambiguos"]} ambíguos, '
                   f'{c["pendurados"]} pendurados.' if denominador
                   else 'Nenhum import interno: não medido, que não é zero.')
        linhas.append(
            f'<div class="r{"" if denominador else " alerta"}"><b>{e(quanto)}</b>'
            f'<span>{e(linguagem)}</span><p>{e(detalhe)}</p></div>')
    return _bloco('Quanto disto foi medido', 'fato',
                  'O quanto confiar na seção de dependências.',
                  f'<div class="retratos">{"".join(linhas)}</div>',
                  classe='n2', largo=True,
                  rodape='O que não resolveu está contado, não escondido: import que o '
                         'resolvedor não casou com arquivo nenhum não vira aresta.')
