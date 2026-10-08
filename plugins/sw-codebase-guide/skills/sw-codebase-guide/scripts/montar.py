#!/usr/bin/env python3
"""Junta inventário e interpretação no `guide.md`.

Duas propriedades inegociáveis:

1. NUNCA afirma ausência de dependentes. O grafo de import não vê injeção de
   dependência, reflexão, rota como string, facade, template nem config — em
   projeto legado isso é a maior parte do acoplamento. Então a saída é sempre
   "N por import, M menções textuais", com a lista do que o grafo não enxerga
   anexada à própria afirmação.
2. É função pura dos arquivos de entrada. Mesmos fatos, mesmo documento, byte a
   byte — sem carimbo de tempo, com ordem estável. É o que faz o diff servir.
"""
import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import conhecimento, julgar, percurso, perguntas  # noqa: E402
from lib import recorte as mod_recorte  # noqa: E402
from lib.arvore import eh_codigo, linguagem_de  # noqa: E402

NIVEIS = {'fato', 'declarado', 'deducao', 'lacuna'}
TETO_SIMBOLOS = 40
DOCUMENTACAO = ('.md', '.txt', '.rst', '.adoc')
SECOES = {'como-entrar', 'depende-de', 'o-que-faz', 'superficie'}

CEGUEIRAS = [
    'injeção de dependência / container',
    'rota como string ("Controller@acao")',
    'reflexão e chamada dinâmica',
    'include de template',
    'acoplamento por SQL ou config',
]


# prefixo que denuncia evidência que NÃO é caminho de arquivo
NAO_CAMINHO = ('commit ', 'http://', 'https://')


def evidencia_valida(ev: str, caminhos: set) -> bool:
    """A evidência aponta para algo que existe? Quatro formas são legítimas.

    O `SKILL.md` documenta `app/Pedido.php:88` e os testes usam `commit 3c5aabb`.
    Uma conferência ingênua recusaria a evidência CORRETA e derrubaria três testes
    que já passam — por isso a guarda nasce conhecendo as quatro formas:
    caminho, caminho com `:linha`, diretório com barra no fim, e não-caminho.
    """
    if ev.startswith(NAO_CAMINHO):
        return True
    alvo = ev.rsplit(':', 1)[0] if re.search(r':\d+$', ev) else ev
    if alvo in caminhos:
        return True
    if alvo.endswith('/'):
        return any(c.startswith(alvo) for c in caminhos)
    return False


# Frases que a skill NUNCA emite: o grafo não sabe o bastante para afirmar
# ausência, e "nada depende disso" é o dano que ela existe para evitar.
# Mora aqui, e não no teste, porque a recusa é do PARSER — duas listas
# divergiriam na primeira vez que alguém acrescentasse uma frase a uma só.
# Em prosa livre sobre pasta o FEMININO é a forma natural ("a pasta não é usada").
# A lista veio de um `guide.md` templatizado, onde só o masculino aparecia; para
# texto do agente ela precisa da flexão, senão a guarda passa ao largo.
PROIBIDAS = ('nada depende', 'sem dependentes', 'nenhum dependente',
             'não é usad', 'nao e usad', 'não são usad', 'nao sao usad',
             'não há dependentes', 'nao ha dependentes', 'sem uso')

PARTES = {'o-que-e', 'percurso', 'mapa', 'orientacoes'}
# `trecho` e `fonte` NÃO são obrigatórios em todo bloco de `o-que-e`: o primeiro
# ancora a parte numa fonte textual, e exigir dos demais empurrava quem escreve a
# pendurar uma citação verdadeira e sem relação embaixo do parágrafo — que na tela
# aparece com cara de evidência, e é pior que não citar. A guarda confere que a
# citação EXISTE, nunca que ela SUSTENTA a frase; esse limite não se resolve com
# mais exigência, se resolve tirando o incentivo.
OBRIGATORIOS = {
    'o-que-e': ('texto', 'evidencia'),
    # `onde` entra como obrigatório no percurso porque o bloco deixou de ser
    # parágrafo e virou PASSO: sem a camada não há onde pôr o passo na trilha, e
    # a travessia de fronteira — derivada de `onde` mudar — simplesmente não
    # nasceria. Um percurso sem camada voltaria a ser a prosa que escondia os
    # arquivos.
    'percurso': ('texto', 'evidencia', 'onde'),
    'mapa': ('texto', 'evidencia'),
    'orientacoes': ('texto', 'evidencia'),
}

TITULOS = {
    'o-que-e': 'O que o produto faz',
    'percurso': 'O percurso de uma funcionalidade',
    'mapa': 'Onde ficam as coisas',
    'orientacoes': 'Para mexer',
}
# a ordem é PEDAGÓGICA: o que é → como funciona de ponta a ponta → onde ficam as
# coisas → como agir. Não é a ordem em que o agente escreve.
ORDEM_DAS_PARTES = ('o-que-e', 'percurso', 'mapa', 'orientacoes')

# Cada parte aponta a seção do relatório técnico: é a mitigação declarada da
# decisão "número livre na narrativa" — não impede divergir, torna descobrível em
# um clique. Cada parte aponta uma seção DIFERENTE: duas apontando a mesma
# (`percurso` e `mapa` iam as duas para "como entrar") entregam o leitor no lugar
# errado, que é pior do que não ter link.
ANCORA = {'o-que-e': 'o-que-o-sistema-faz',
          'percurso': 'superfície-pública',
          'mapa': 'como-entrar',
          'orientacoes': 'o-que-depende-do-quê'}


def _normalizar(texto: str) -> str:
    """Colapsa espaço, tabulação e quebra de linha num espaço só.

    Sem isto a guarda do trecho nasce morta: README quebrado em 80 colunas faz
    qualquer frase citada atravessar linhas, a substring exata falha, e o agente
    aprende a citar fragmentos de quatro palavras para escapar — o oposto do que
    se quer.
    """
    return ' '.join(texto.split())


def _conferir_trecho(bloco: dict, textos: dict) -> None:
    """O pior modo de falha da parte "o que o produto faz" não é falsidade: é ser
    fluente, verdadeira e INÚTIL. *"O sistema gerencia clientes e pedidos, com
    um funil de vendas"* passa em qualquer conferência de caminho, e o dev já
    sabia disso lendo o nome das pastas. Trecho literal não consegue ser
    vazio-e-fluente: ou está escrito na fonte, ou não está."""
    fonte = bloco['fonte']
    if fonte not in textos:
        raise ValueError(
            f'fonte não é fonte textual reconhecida: {fonte!r} — '
            f'use README, CLAUDE.md, docs/ ou ADR')
    if textos[fonte].get('omitido'):
        # sem esta guarda a mensagem seria "o trecho não aparece em X" — e mandaria
        # procurar erro na citação quando o conteúdo é que não foi lido
        raise ValueError(
            f'o conteúdo de {fonte} não entrou no inventário ({textos[fonte]["motivo"]}); '
            f'cite uma fonte lida ou leia este arquivo e confira o trecho à mão')
    if _normalizar(bloco['trecho']) not in _normalizar(textos[fonte]['conteudo']):
        raise ValueError(
            f'o trecho citado não aparece em {fonte}: {bloco["trecho"][:60]!r}')


ROTULO_DO_SALTO = re.compile(r'(?i)^\s*n[aã]o\s+rastreado\s*[:\-—]\s*')


def limpar_salto(salto: str) -> str:
    """Tira o rótulo que o documento já põe.

    "Não rastreado" é a frase natural de quem escreve o salto, e os dois emissores
    carimbam o rótulo por conta própria — o `leia-me.md` no texto, o HTML por CSS.
    Rodando num projeto real saiu `**Não rastreado:** Não rastreado: o que acontece…`.
    Limpar aqui, no leitor, conserta os dois de uma vez.
    """
    return ROTULO_DO_SALTO.sub('', salto).strip()


def _ler_narrativa(dados: dict, caminhos: set, textos: dict) -> list:
    blocos = dados.get('narrativa', [])
    for b in blocos:
        parte = b.get('parte')
        if parte not in PARTES:
            raise ValueError(f'parte inválida ou ausente: {parte!r}')
        for campo in OBRIGATORIOS[parte]:
            if not b.get(campo):
                raise ValueError(f'{parte}: campo obrigatório ausente: {campo}')
        baixo = b['texto'].lower()
        for frase in PROIBIDAS:
            if frase in baixo:
                raise ValueError(
                    f'{parte}: frase proibida no texto ({frase!r}) — ausência de '
                    f'dependentes nunca é afirmada')
        # `saltos` é obrigatório no percurso MESMO VAZIO: a lista vazia afirma
        # "segui do clique até o banco sem buraco nenhum", que é afirmação forte.
        # Omitir o campo deixaria "não tentei" indistinguível de "segui inteiro".
        if parte == 'percurso' and b['onde'] not in percurso.CAMADAS:
            raise ValueError(
                f'percurso: camada inválida em `onde`: {b["onde"]!r} — use uma de '
                + ' · '.join(percurso.CAMADAS))
        if parte == 'percurso' and 'saltos' not in b:
            raise ValueError(
                'percurso: o campo `saltos` é obrigatório, mesmo vazio — lista vazia '
                'afirma "segui do clique até o banco sem buraco", e omitir o campo '
                'deixaria "não tentei" indistinguível disso')
        # `ordem` precisa ser inteiro: `ordem = "dois"` passava por todas as
        # validações e explodia no `sorted` com TypeError e traceback — o parser
        # tem que recusar com motivo, nunca estourar
        if 'ordem' in b and not isinstance(b['ordem'], int):
            raise ValueError(
                f'{parte}: ordem precisa ser um número inteiro, veio {b["ordem"]!r}')
        if b.get('saltos'):
            b['saltos'] = [limpar_salto(s) for s in b['saltos']]
        if parte == 'o-que-e' and b.get('trecho'):
            if not b.get('fonte'):
                raise ValueError('o-que-e: bloco com `trecho` precisa de `fonte`')
            _conferir_trecho(b, textos)
        for ev in b['evidencia']:
            if not evidencia_valida(ev, caminhos):
                raise ValueError(f'evidência não existe no projeto: {ev!r}')
    # a parte "o que o produto faz" continua ancorada: sem nenhuma citação ela vira
    # prosa fluente sem lastro, que é o modo de falha que a guarda existe para pegar
    o_que_e = sorted((b for b in blocos if b['parte'] == 'o-que-e'),
                     key=lambda b: b.get('ordem', 0))
    if o_que_e and not o_que_e[0].get('trecho'):
        raise ValueError(
            'o-que-e: o primeiro bloco precisa de `trecho` e `fonte` — é ele que '
            'ancora a parte numa fonte textual. Os blocos seguintes podem se '
            'sustentar só na evidência de código')
    return sorted(blocos, key=lambda b: (b['parte'], b.get('ordem', 0)))


def montar_leia_me(inv: dict, narrativa: list) -> str:
    """O documento humano, ao lado do relatório técnico.

    Markdown aqui é para versionar e dar diff; quem vai LER de ponta a ponta abre
    o `leia-me.html`, que o `imprimir.py` monta do mesmo material.
    """
    L = []
    A = L.append
    A('# Guia para quem vai mexer\n')
    dito = mod_recorte.frase(inv.get('escopo') or {})
    if dito:
        A(f'> Cobre {dito[1]} `{dito[0]}`, não o projeto inteiro.\n')
    A('> Documento escrito a partir do código. O relatório técnico, com a evidência')
    A('> de cada afirmação, está em [`guide.md`](guide.md).\n')

    por_parte = {}
    for b in narrativa:
        por_parte.setdefault(b['parte'], []).append(b)

    for parte in ORDEM_DAS_PARTES:
        A(f'## {TITULOS[parte]}\n')
        # link curto, não frase: a mesma sentença repetida sob quatro títulos
        # vira ruído e o olho aprende a pular justamente o que deveria seguir
        A(f'[→ a evidência, no relatório técnico](guide.md#{ANCORA[parte]})\n')
        blocos = sorted(por_parte.get(parte, []), key=lambda b: b.get('ordem', 0))
        if not blocos:
            A('*A interpretação não escreveu esta parte.*\n')
            continue
        if parte == 'percurso':
            _percurso_md(A, blocos)
            continue
        for b in blocos:
            A(b['texto'] + '\n')
            if b.get('trecho'):
                # o literal ao lado da paráfrase: é assim que o leitor confere
                A(f'> {b["trecho"]}')
                A(f'> — `{b["fonte"]}`\n')
            for salto in b.get('saltos', []):
                A(f'- **Não rastreado:** {salto}')
            if b.get('saltos'):
                A('')
    return '\n'.join(L)


def _candidatos_a_percurso(inv: dict) -> list:
    """Por onde começar a rastrear, e o tamanho do ponto cego.

    A skill dizia não detectar entrypoint, enquanto a `superficie` já os listava:
    o que faltava era usá-los para PROPOR. E a contagem das entradas que não
    alcançam nada pelo import é dado, não rodapé — num projeto real eram 17 de
    49, e o leitor precisa saber disso antes de confiar no grafo para rastrear.
    """
    p = inv.get('percursos') or {}
    candidatos = p.get('candidatos') or []
    if not candidatos:
        return []
    L, A = [], (lambda s: L.append(s))
    A('Por onde começar a rastrear — as entradas que mais exercitam o sistema, '
      'por número de papéis distintos que alcançam:\n')
    for c in candidatos:
        termo = f' (`{c["termo"]}`)' if c.get('termo') else ''
        A(f'- `{c["entrada"]}`{termo} — alcança {c["alcanca"]} arquivos em '
          f'{len(c["papeis"])} papéis: {" · ".join(c["papeis"])}  [fato]')
    A('')
    if p.get('entradas_sem_alcance'):
        A(f'**{p["entradas_sem_alcance"]} das {p["entradas"]} entradas não alcançam '
          f'nenhum arquivo pelo import.** Quem as liga ao resto faz por um caminho '
          f'que o grafo não vê.  [fato]\n')
    A(f'> {p["limite"]}.\n')
    return L


def _fatia(escopo: dict) -> list:
    """O que é só desta funcionalidade, e o que é de todo mundo.

    É o que paga o recorte por funcionalidade. Medindo um projeto real, o
    arquivo mais importante da fatia era também o mais compartilhado — o helper
    onde mora a regra do formulário, com 29 importadores de fora. Esconder a
    conta faria o leitor mudar esse arquivo achando que mexia só na fatia.
    """
    if escopo.get('tipo') != 'funcionalidade':
        return []
    L, A = [], (lambda s: L.append(s))
    A('### O que é desta funcionalidade\n')
    if escopo.get('eh_area'):
        A(f'> **Isto é uma área, não uma funcionalidade.** O termo '
          f'`{escopo["funcionalidade"]}` leva {escopo["nucleo"]} arquivos no nome: '
          f'é como o projeto chama uma parte inteira dele. Recorte mais fino, ou '
          f'use `--area`.  [fato]\n')
    compartilhado = escopo.get('compartilhado') or []
    A(f'- **{escopo["nucleo"]}** arquivos levam o nome no caminho — é o núcleo.  [fato]')
    if escopo['alcance']:
        A(f'- **{escopo["alcance"]}** arquivos a mais o núcleo importa, e quase ninguém '
          f'de fora usa.  [fato]')
    elif not compartilhado:
        # com zero nos dois, "0 arquivos a mais, e quase ninguém de fora usa" vira
        # absurdo — e esconde o fato maior, que é o núcleo não importar nada fora
        # de si. Achado rodando num projeto nunca visto, com a suíte verde.
        A('- O núcleo **não importa nada** fora de si.  [fato]')
    else:
        A('- Fora do núcleo, tudo que ele importa é **compartilhado** com o resto do '
          'sistema.  [fato]')
    A(f'- **{escopo["usada_por"]}** arquivos de fora importam a fatia: é o que quebra '
      f'se a interface dela mudar.  [fato]\n')
    if not compartilhado:
        return L
    A('Estes a funcionalidade usa, mas são **de todo mundo** — mexer neles sai do '
      'recorte:\n')
    for c in compartilhado[:10]:
        A(f'- `{c["caminho"]}` — {c["importadores"]} arquivos de fora o importam')
    if len(compartilhado) > 10:
        A(f'- … e mais {len(compartilhado) - 10}')
    A('')
    return L


def _percurso_md(A, blocos: list) -> None:
    """O percurso em passos, com o arquivo de cada um impresso.

    O que mudou e por quê: antes isto era `A(b['texto'])` como qualquer outra
    parte, e a `evidencia` — validada contra o projeto, linha por linha — nunca
    chegava à página. Quem lia a história tinha que ir caçar os arquivos no
    relatório técnico, que é exatamente o trabalho que o documento existe para
    poupar.
    """
    passos = percurso.em_passos(blocos)
    quantas = percurso.travessias(passos)
    camadas = percurso.camadas_usadas(passos)
    A(f'> {len(passos)} passos · {len(camadas)} camadas '
      f'({" · ".join(camadas)}) · {quantas} '
      f'{"fronteira" if quantas == 1 else "fronteiras"}\n')
    for i, p in enumerate(passos, 1):
        if p['atravessa']:
            de, para = p['atravessa']
            A(f'↳ **Atravessa:** {de} → {para}\n')
        linha = f'**{i} · {p["onde"]}** — {p["texto"]}'
        if p['evidencia']:
            # os dois espaços no FIM da linha são a quebra dura do Markdown; numa
            # linha só deles seriam espaço em branco solto, que o lint acusa e o
            # renderizador ignora
            A(linha + '  ')
            A(' · '.join(f'`{ev}`' for ev in p['evidencia']))
        else:
            A(linha)
        A('')
        for salto in p['saltos']:
            A(f'- **Não rastreado:** {salto}')
        if p['saltos']:
            A('')


def _ler_interpretacao(caminho: Path, caminhos: set | None = None) -> list:
    if not caminho.exists():
        return []
    dados = tomllib.loads(caminho.read_text('utf-8'))
    afirmacoes = dados.get('afirmacao', [])
    for a in afirmacoes:
        if a.get('secao') not in SECOES:
            raise ValueError(f'secao inválida ou ausente: {a.get("secao")!r}')
        if a.get('nivel') not in NIVEIS:
            raise ValueError(f'nivel inválido: {a.get("nivel")!r}')
        if a['nivel'] == 'lacuna' and not a.get('motivo'):
            raise ValueError(f'lacuna sem motivo: {a.get("texto")!r}')
        if a['nivel'] != 'lacuna' and not a.get('evidencia'):
            raise ValueError(
                f'afirmacao sem evidencia e sem ser lacuna: {a.get("texto")!r}')
        # a conferência é o que impede prosa plausível de entrar com citação
        # inventada — o modo de falha mais caro, porque quem recebe o documento
        # leva a frase ao cliente como se fosse apurada
        for ev in a.get('evidencia', []):
            if caminhos is not None and not evidencia_valida(ev, caminhos):
                raise ValueError(f'evidência não existe no projeto: {ev!r}')
    return afirmacoes


def _como_foi_detectada(componente: dict) -> str:
    """Stack sem manifesto é detectada por contagem de extensão.

    Imprimir `manifesto` cru colocaria a palavra `None` no documento — dizer COMO
    foi detectada é o que o leitor precisa para saber o quanto confiar.
    """
    manifesto = componente.get('manifesto')
    if manifesto:
        return f'`{manifesto}`'
    return f'sem manifesto; detectada por {componente.get("por", "contagem de arquivos")}'


PISO_RESOLUCAO = 0.70     # abaixo disto, ranking vira lacuna
TETO_RANKING = 15


def _taxa(c: dict):
    """(resolvidos, denominador) — ou (0, 0) quando não houve import interno.

    A fórmula escrita uma vez, porque sem ela dois leitores chegam a números
    diferentes: `externos` fica FORA dos dois lados de propósito, e é a conta mais
    delicada daqui — inflar aquele balde inflaria a taxa.
    """
    resolvidos = (c['relativos'] + c['sufixo_unico'] + c['base_provada']
                  + c['config_conferida'])
    return resolvidos, resolvidos + c['ambiguos'] + c['pendurados'] + c['nao_resolvidos']


def _dependentes(inv: dict) -> list:
    """Quem importa quem, por linguagem — ou a lacuna, quando a medição foi fraca.

    Substitui a lista por símbolo que existia antes: ela vinha de `mencoes` e casava
    PALAVRA, o que numa base em português devolvia `banco` e `caminho` com centenas
    de menções. Com aresta real a pergunta tem resposta direta.
    """
    from lib.imports import POR_EXTENSAO

    resolucao = inv['imports'].get('resolucao') or {}
    barris = set(inv['imports'].get('barris') or [])
    # a entrada é POR LINGUAGEM, pela extensão de quem importa: sem isso o bloco
    # `js` de um monorepo listava arquivos `.php` no topo do ranking, porque a
    # contagem era global e o título dizia outra coisa
    entrada = {}
    for aresta in inv['imports']['arestas']:
        ling = POR_EXTENSAO.get(Path(aresta['de']).suffix.lower())
        if ling:
            entrada.setdefault(ling, {}).setdefault(aresta['para'], set()).add(aresta['de'])

    linhas, houve_ranking = [], False
    # A indisponibilidade sai no preâmbulo da seção — MENOS quando o preâmbulo é
    # suprimido, que é o caso de não haver aresta nenhuma (ali, cegueiras mais
    # indisponibilidade mais lacuna dizem a mesma coisa três vezes). Então ela sai
    # aqui, e só aqui. Imprimir nos dois lugares deu vinte linhas de lacuna repetida
    # antes de qualquer conteúdo num projeto real: a v0.1.1 por outro caminho.
    indisponivel = inv['imports'].get('indisponivel') or []
    if indisponivel and not inv['imports']['arestas']:
        for item in indisponivel:
            linhas.append(f'Grafo de import indisponível para **{item["stack"]}**: '
                          f'{item["motivo"]}  [lacuna]\n')
    for linguagem, contagem in sorted(resolucao.items()):
        resolvidos, denominador = _taxa(contagem)
        linhas.append(f'### {linguagem}\n')
        if denominador == 0:
            linhas.append(f'Nenhum import interno em {linguagem} — não medido, que '
                          f'não é o mesmo que zero.  [lacuna]\n')
            continue
        pct = round(resolvidos * 100 / denominador)
        if resolvidos / denominador < PISO_RESOLUCAO:
            linhas.append(
                f'A resolução de import ficou em **{pct}%** ({resolvidos} de '
                f'{denominador}), abaixo do piso de {round(PISO_RESOLUCAO * 100)}%. '
                f'Um ranking sobre esse grafo teria cara de fato.\n')
            linhas.append(f'*Quem depende de quem em {linguagem} continua por '
                          f'apurar.*  [lacuna]\n')
            continue
        # o barril é um corredor, não um destino: com `export … from` no extrator,
        # todo `@/utils` resolve nele e o topo viraria "300 arquivos importam
        # index.ts" — verdadeiro, inútil, e com o arquivo que a pessoa precisa abrir
        # a dois saltos, que o não-objetivo "sem análise transitiva" proíbe seguir
        # o ranking é de CÓDIGO: a aresta para uma imagem é real e fica no grafo,
        # mas num projeto real um `.png` ocupava uma das quinze vagas da lista que
        # existe para mostrar acoplamento
        ranking = sorted(((alvo, des) for alvo, des in entrada.get(linguagem, {}).items()
                          if alvo not in barris
                          and eh_codigo(linguagem_de(Path(alvo)))),
                         key=lambda t: (-len(t[1]), t[0]))
        linhas.append(f'Resolvidos {resolvidos} de {denominador} imports '
                      f'({pct}%).  [fato]\n')
        houve_ranking = True
        for alvo, des in ranking[:TETO_RANKING]:
            plural = 'arquivo importa' if len(des) == 1 else 'arquivos importam'
            linhas.append(f'- {len(des)} {plural} diretamente `{alvo}`')
        if len(ranking) > TETO_RANKING:
            linhas.append(f'- … e mais {len(ranking) - TETO_RANKING}')
        linhas.append('')
    if not linhas:
        return ['*Quem depende de quem continua por apurar.*  [lacuna]']
    if not houve_ranking:
        # sem lista, a ressalva repetiria o que a lacuna acima já disse
        return linhas
    # a ressalva precisa dizer que a lista é parcial SEM usar as frases de
    # `PROIBIDAS` — "nada depende" é a primeira delas, e o teste do documento
    # montado roda a lista inteira sobre o `guide.md`
    # as cinco cegueiras já estão no preâmbulo da seção — repeti-las aqui seria a
    # terceira vez que o documento diz a mesma coisa na mesma página
    linhas.append('Esta lista diz quem importa **diretamente**: não é transitiva, e um '
                  'arquivo ausente dela pode ter dependentes que esta medição não '
                  'enxerga. O grafo textual, que casa o nome como palavra, fica no '
                  '`inventory.json`, na seção `mencoes`, para quem quiser olhar à mão '
                  '— ele não entra aqui porque numa base em português devolve `banco` '
                  'e `caminho` às centenas sem haver relação de código.')
    return linhas


def _julgamento(inv: dict, respostas: list) -> list:
    """As quatro perguntas de quem recebe um projeto.

    É a única seção que OPINA, e por isso cada bloco segue a mesma forma: sinal
    medido, limiar escrito, e a frase do que ele não diz. Nada de nota — uma nota
    vira meta, e meta vira teatro.
    """
    j = inv.get('julgamento') or {}
    if not j:
        return []
    L = []
    def A(linha=''):
        L.append(linha)

    A('## Antes de mexer\n')

    d = j['dossie']
    A('**Vale manter ou reescrever?** Esta skill não responde, e isso é desenho: a')
    A('resposta depende de quanto custa reescrever e do que o negócio depende, e o')
    A('código não contém nenhum dos dois. O que dá para pôr na mesa é isto —\n')
    if d['autores'] is None:
        A('- autoria **não apurada** — não há repositório git')
    else:
        um = d['autores'] == 1
        A(f'- **{d["autores"]} pessoa{"" if um else "s"}** '
          f'{"commitou" if um else "commitaram"}, em {d["commits"]} commits')
    parado = d['semanas_parado'] or 0
    A(f'- **{d["semanas_de_vida"] or "?"} semanas de vida**, '
      + ('**mexido esta semana**' if parado == 0 else
         f'**parado há {parado} semana{"" if parado == 1 else "s"}**'))
    A(f'- **{d["arquivos_de_codigo"]} arquivos de código** em {d["stacks"]} stack(s), '
      f'**{d["pct_teste"]}% é teste**')
    A(f'- import medido em: {", ".join(d["linguagens_medidas"]) or "nenhuma linguagem"}')
    A(f'\n*Falta, e o código não tem: {d["falta"]}.*  [lacuna]\n')

    if j['perigo']:
        A('### Onde é mais caro errar\n')
        A(f'Os três sinais **juntos**: mais de {julgar.MIN_DEPENDENTES} arquivos')
        A(f'importando, mais de {julgar.MIN_COMMITS} commits de histórico, e nenhum')
        A('teste com o mesmo nome. Isoladamente nenhum diz nada — arquivo muito')
        A('importado pode estar estável há anos.  [dedução]\n')
        for a in j['perigo'][:10]:
            A(f'- `{a["caminho"]}` — {a["dependentes"]} dependentes, '
              f'{a["mudancas"]} commits, sem teste')
        if len(j['perigo']) > 10:
            A(f'- … e mais {len(j["perigo"]) - 10}')
        A('')

    if j['risco']:
        A('### Risco visível\n')
        A('Só o que se vê sem rede e sem executar nada. **O valor de uma variável')
        A('nunca é lido**: estes achados falam de nome e de arquivo.  [fato]\n')
        for r in j['risco']:
            A(f'- `{r["onde"]}` — {r["o_que"]}')
        A('')

    ja_respondidos = {r['sobre'] for r in respostas}
    abertos = [a for a in j['sem_alcance'] if a['caminho'] not in ja_respondidos]
    if abertos:
        A('### Ninguém parece usar — ainda é usado?\n')
        A('**São perguntas, não veredito.** Nenhum import alcança estes arquivos e')
        A(f'ninguém os toca há mais de {julgar.DIAS_PARADO // 365} ano, mas o grafo')
        A('não vê injeção de dependência, rota como string nem reflexão. Papel que o')
        A('framework instancia por convenção já ficou de fora desta lista.  [dedução]\n')
        for a in abertos[:10]:
            A(f'- `{a["caminho"]}` — {a["dias_parado"]} dias sem mudança')
        if len(abertos) > 10:
            A(f'- … e mais {len(abertos) - 10}')
        A('')

    if respostas:
        A('### Já perguntamos\n')
        A('O que alguém respondeu, e que o código não diz. Sai da lista acima para o')
        A('documento melhorar a cada rodada — e fica aqui, com nome e data, porque')
        A('resposta sem quem a deu não dá para conferir depois.  [confirmado]\n')
        for r in respostas:
            aviso = ('' if not r.get('mudou_depois') else
                     f' ⚠ o arquivo mudou em {r["mudou_depois"]}, depois desta '
                     f'resposta — pode ter voltado a valer')
            A(f'- `{r["sobre"]}` — *{r["pergunta"]}* {r["resposta"]} '
              f'— **{r["quem"]}**, {r["quando"]}{aviso}')
        A('')
    return L


def _escrever(L: list, afirmacoes: list, secao: str) -> None:
    """Despeja as afirmações daquela seção. Seção vazia diz que está vazia.

    Toda seção publicada no contrato precisa ter consumidor aqui: a primeira versão
    só lia `o-que-faz`, e o que o agente escrevia para `como-entrar` e `superficie`
    sumia sem erro — trabalho feito, conteúdo evaporado.
    """
    do_agente = [a for a in afirmacoes if a.get('secao') == secao]
    if not do_agente:
        L.append('*A interpretação não escreveu nada aqui.*  [lacuna: seção não interpretada]\n')
        return
    # ORDEM DE ESCRITA, não alfabética: ordenar por texto é ordenar por acaso, e
    # num teste real a frase mais importante da seção caiu em último lugar porque
    # começava com "É". Quem escreve a interpretação ordena por importância.
    # o nível no TOML é sem acento (é chave de formato); o RÓTULO impresso é
    # acentuado, porque é texto para gente ler
    rotulos = {'deducao': 'dedução'}
    for a in do_agente:
        L.append(f'- {a["texto"]}  [{rotulos.get(a["nivel"], a["nivel"])}]')
        for e in a.get('evidencia', []):
            L.append(f'    ↳ `{e}`')
    L.append('')


def _no_recorte(inv: dict) -> set:
    """Os arquivos desta rodada, para marcar a ponta que está FORA.

    Era um teste de prefixo (`caminho.startswith(area + '/')`), e prefixo só
    descreve área: uma funcionalidade é um conjunto espalhado — o cadastro mora
    em duas aplicações — e toda ponta dela sairia marcada como "fora". A árvore
    do inventário JÁ é o recorte, e serve aos dois casos.
    """
    return {a['caminho'] for a in inv.get('arvore') or []}


def montar(inv: dict, afirmacoes: list, respostas: list | None = None,
           narrativa: list | None = None) -> str:
    respostas = respostas or []
    L = []
    A = L.append
    A('# Guia do projeto\n')
    A('> Documento gerado por leitura do código. Cada afirmação carrega o nível de')
    A('> confiança: **fato** (medido) · **declarado** (humano escreveu antes) ·')
    A('> **dedução** (inferida, com evidência) · **lacuna** (não apurado, com motivo)')
    A('> · **confirmado** (alguém respondeu, e o nome está junto).\n')

    escopo = inv.get('escopo') or {}
    dito = mod_recorte.frase(escopo)
    if dito:
        rotulo, o_que, n = dito
        plural = '' if n == 1 else 's'
        A(f'> **Recorte:** este documento cobre {o_que} `{rotulo}` '
          f'({n} arquivo{plural}), não o projeto inteiro.\n')
    L.extend(_fatia(escopo))

    L.extend(_julgamento(inv, respostas))
    A('## Como entrar\n')
    for c in inv['stacks']:
        marca = '  *(fora da área, herdado da raiz)*' if c.get('de_fora_da_area') else ''
        A(f'- **{c["stack"]}** em `{c["caminho"]}` — {_como_foi_detectada(c)}  [fato]{marca}')
    if not inv['stacks']:
        A('- nenhum manifesto reconhecido na raiz  [lacuna: o projeto não declara stack '
          'por manifesto conhecido]')
    A('')
    # "2.036 arquivos" se lê como 2.036 arquivos de CÓDIGO; num projeto real metade
    # eram PNG e SVG. A afirmação estava correta e comunicava errado. O predicado
    # mora no `pagina.py` e vale para os dois documentos: markdown e YAML entram no
    # segundo número, que é onde o bloco de arquivos maiores já os punha.
    codigo = sum(1 for a in inv['arvore'] if eh_codigo(a['linguagem']))
    resto = len(inv['arvore']) - codigo
    A(f'{codigo} arquivos de código e {resto} de imagem, texto ou configuração '
      f'(fora `vendor/`, `node_modules/`, cache e gerados).  [fato]\n')
    for arquivo, chaves in inv['ambiente'].items():
        A(f'`{arquivo}` declara {len(chaves)} variáveis — **só os nomes**, '
          f'nunca os valores:  [fato]')
        A('`' + '` · `'.join(chaves) + '`\n')
    _escrever(L, afirmacoes, 'como-entrar')

    A('## O que depende do quê\n')
    # O preâmbulo das cegueiras serve para qualificar uma LISTA. Quando não há lista
    # — a seção inteira virou lacuna —, imprimir as cinco cegueiras, mais a
    # indisponibilidade, mais a lacuna é dizer a mesma coisa três vezes.
    if not (not inv['imports']['arestas'] and inv['imports']['indisponivel']):
        # A frase-guarda NÃO pode conter nenhuma das frases proibidas — a primeira
        # versão dizia «não existe "nada depende disso" aqui» e reprovava o próprio teste.
        A('Duas leituras cruzadas. **Ausência de dependentes nunca é afirmada neste**')
        A('**documento**: o grafo de import não enxerga o seguinte —\n')
        for cegueira in CEGUEIRAS:
            A(f'- {cegueira}')
        A('')
        for item in inv['imports']['indisponivel']:
            A(f'> Grafo de import indisponível para **{item["stack"]}**: '
              f'{item["motivo"]}  [lacuna]')
            A('')
    L.extend(_dependentes(inv))
    A('')
    _escrever(L, afirmacoes, 'depende-de')

    A('### O que muda junto\n')
    dentro = _no_recorte(inv)
    parcial = mod_recorte.frase(inv.get('escopo') or {}) is not None
    h = dict(inv['historia'])
    # O `git log` devolve caminho HISTÓRICO: arquivo apagado ou renomeado continua
    # na lista. Num projeto real eram 16 caminhos que não existem hoje, e o leitor
    # ia procurá-los. O par vale pelo que ensina sobre o código de AGORA.
    existe = set(inv.get('caminhos_do_projeto') or [])
    if existe:
        vivos = [c for c in h['co_mudanca']
                 if all(a in existe for a in c['arquivos'])]
        sumidos = len(h['co_mudanca']) - len(vivos)
        h['co_mudanca'] = vivos
    else:
        sumidos = 0
    # Decide pelo DADO, não pela lacuna. Depois que a busca por sub-repositórios
    # entrou, `lacuna` passou a significar duas coisas — "não há dado" e "há dado,
    # com ressalva" — e o documento escondia 40 pares de co-mudança que tinha.
    if not h['co_mudanca']:
        A(f'Não apurado: {h["lacuna"]}.  [lacuna]\n')
        A('Sem histórico, a concentração de risco é substituída por sinais estáticos —')
        A('número de menções, tamanho do arquivo e quantas stacks o tocam.\n')
    else:
        if h['lacuna']:
            A(f'> Ressalva: {h["lacuna"]}.  [lacuna parcial]\n')
        de_onde = ' do projeto todo' if parcial else ''
        fora = (f'; {sumidos} par(es) ficaram de fora por citarem arquivo que não '
                f'existe mais' if sumidos else '')
        A(f'De {h["commits"]} commits{de_onde} '
          f'({h["commits_descartados"]} descartados por tocarem arquivos '
          f'demais{fora}).  [fato]\n')
        for c in h['co_mudanca'][:20]:
            # a ponta que está FORA da área sai marcada: "mexer aqui mexe lá fora"
            # só ensina alguma coisa se o leitor souber qual é o lá fora
            marcas = [f'`{a}`' + ('' if not parcial or a in dentro else ' *(fora)*')
                      for a in c['arquivos']]
            A(f'- {marcas[0]} + {marcas[1]} — {c["vezes"]}x')
        A('')

    A('## Superfície pública\n')
    sup = inv['superficie']
    if not sup:
        A('Nenhuma pasta de convenção conhecida (`routes/`, `migrations/`, `Jobs/`…).')
        A('  [lacuna: o projeto não segue convenção de caminho reconhecida]\n')
    else:
        A('Reconhecida por **convenção de caminho** — é indício, não prova.  [dedução]\n')
        L.extend(_candidatos_a_percurso(inv))
        for tipo in ('rota', 'comando', 'job', 'migration'):
            itens = [i for i in sup if i['tipo'] == tipo]
            if not itens:
                continue
            A(f'**{tipo}** ({len(itens)}), por `{itens[0]["por"]}`:')
            for i in itens[:10]:
                A(f'- `{i["caminho"]}`')
            if len(itens) > 10:
                A(f'- … e mais {len(itens) - 10}')
            A('')
    _escrever(L, afirmacoes, 'superficie')

    A('## O que o sistema faz\n')
    _escrever(L, afirmacoes, 'o-que-faz')

    A('## Perguntas em aberto\n')
    A('O que o código não respondeu — pauta para levar a quem conhece o sistema.\n')
    for a in sorted((x for x in afirmacoes if x['nivel'] == 'lacuna'),
                    key=lambda x: x['texto']):
        A(f'- {a["texto"]} — *{a["motivo"]}*')
    # Pergunta fixa só faz sentido enquanto ninguém respondeu. Repetir "qual é o
    # propósito?" logo abaixo de três afirmações `declarado` com fonte citada faz o
    # documento se contradizer na mesma página.
    # Qualquer nível MENOS lacuna conta como resposta. A versão anterior exigia
    # `fato` ou `declarado`, e foi escrita quando propósito só podia vir de fonte
    # textual — regra que caiu no spike da v0.2.0. Hoje a resposta mais comum é uma
    # dedução de evidências convergentes, e o documento perguntava de novo três
    # parágrafos depois de responder.
    # As derivadas vêm DEPOIS das lacunas do agente e ANTES das genéricas: elas
    # chegam com o número na mão, que é o que transforma a seção em pauta de
    # reunião em vez de formulário.
    derivadas = perguntas.derivar(inv, julgar.linguagens_confiaveis(inv))
    for d in derivadas:
        A(f'- {d["pergunta"]} — *{d["porque"]}*')

    respondido = {a['secao'] for a in afirmacoes if a['nivel'] != 'lacuna'}
    if any(b['parte'] == 'o-que-e' for b in (narrativa or [])):
        respondido.add('o-que-faz')     # a narrativa responde, com trecho literal
    if not h['co_mudanca']:
        A('- Existe histórico de versionamento deste projeto em outro lugar?')
    if 'o-que-faz' not in respondido:
        A('- Qual é o propósito de negócio do sistema, e quem o usa?')
    if 'como-entrar' not in respondido:
        A('- Como se sobe este projeto do zero?')
    # A pergunta não pode CONTER a forma de uma afirmação de ausência: quem lê
    # de relance guarda "a pasta não é usada" e esquece o ponto de interrogação.
    # A própria guarda `PROIBIDAS` pegava esta linha, e estava certa.
    #
    # E ela só sai quando NÃO houve pergunta derivada sobre arquivo parado: a
    # genérica logo abaixo de três perguntas que nomeiam arquivo e dias parados
    # faz a seção inteira parecer formulário.
    if not any('parado há' in d['pergunta'] for d in derivadas):
        A('- Estas pastas ainda são usadas? Alguma pode ser apagada?')
    A('')
    return '\n'.join(L)


def main() -> int:
    p = argparse.ArgumentParser(description='Monta o guide.md a partir do inventário.')
    p.add_argument('--dir', required=True, help='diretório com inventory.json')
    args = p.parse_args()

    base = Path(args.dir).resolve()
    inventario = base / 'inventory.json'
    if not inventario.exists():
        print(f'não achei {inventario} — rode varrer.py antes', file=sys.stderr)
        return 2

    try:
        inv = json.loads(inventario.read_text('utf-8'))
        # `caminhos` vem de `caminhos_do_projeto`, NÃO de `arvore`: com área
        # escolhida a árvore está recortada, e citar a ponta de fora é legítimo —
        # é exatamente o que a seção de orientações existe para dizer.
        # as fontes textuais entram junto: `.claude/CLAUDE.md` é lido pela skill
        # porque num projeto real é a única documentação que existe, mas a pasta é
        # podada da árvore — e sem esta união a guarda recusava, dizendo "não existe
        # no projeto", um arquivo que o próprio inventário tinha acabado de ler
        caminhos = set(inv.get('textos') or {}) | set(inv.get('caminhos_do_projeto')
                       or [a['caminho'] for a in inv.get('arvore', [])])
        afirmacoes = _ler_interpretacao(base / 'interpretation.toml', caminhos)
        arquivo = base / 'interpretation.toml'
        dados = tomllib.loads(arquivo.read_text('utf-8')) if arquivo.exists() else {}
        narrativa = _ler_narrativa(dados, caminhos, inv.get('textos') or {})
    except ValueError as erro:
        print(f'interpretation.toml inválido: {erro}', file=sys.stderr)
        return 2

    # as DUAS montagens antes de qualquer escrita: recusa pela metade deixaria o
    # `guide.md` novo ao lado de um `leia-me.md` velho, e ninguém saberia qual
    # o conhecimento humano é lido AQUI e envelhecido contra a data de mudança de
    # cada arquivo: resposta dada antes da última alteração vira suspeita
    try:
        respostas = conhecimento.envelhecidas(
            conhecimento.ler(base),
            {c: {'ultima': d} for c, d in (inv.get('mudanca_por_arquivo') or {}).items()})
    except ValueError as erro:
        print(erro, file=sys.stderr)
        return 2
    texto_guia = montar(inv, afirmacoes, respostas, narrativa)
    texto_leia_me = montar_leia_me(inv, narrativa)
    (base / 'guide.md').write_text(texto_guia, encoding='utf-8')
    (base / 'leia-me.md').write_text(texto_leia_me, encoding='utf-8')
    print(f'{base / "guide.md"}')
    print(f'{base / "leia-me.md"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
