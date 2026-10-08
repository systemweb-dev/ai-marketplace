"""O percurso em passos: a camada de cada um, e onde ele atravessa fronteira.

Antes desta versão o percurso era PROSA: três ou quatro parágrafos corridos com
`evidencia` validada e nunca impressa. Quem lia recebia a história e tinha que ir
caçar os arquivos no relatório técnico — a informação estava apurada, conferida
contra o projeto, e invisível. Aqui ela vira passo, e o arquivo aparece embaixo
de cada um.

**A travessia não é declarada, é derivada.** Ela existe quando `onde` muda entre
dois passos consecutivos, e só isso. Deixar o autor declarar "aqui atravessa
repositório" abriria a porta para o documento afirmar uma fronteira que os dados
não mostram; derivar faz a afirmação ser exatamente o que está escrito na
interpretação, nem uma vírgula além.

O desenho veio de mockup aprovado em 07/10 (variação "Trilha"): a fronteira
INTERROMPE o fio, porque atravessar aplicação é o evento mais caro de quem
acabou de receber o projeto e o que a prosa escondia melhor.
"""

# A ordem é a do caminho típico de um pedido, e é ela que o documento usa para
# nomear a travessia ("navegador → servidor"). Não é hierarquia nem camada de
# arquitetura: é onde o passo RODA, que é o que o leitor precisa saber para
# abrir o arquivo certo.
CAMADAS = ('navegador', 'servidor', 'fila', 'banco', 'externo')

# Um glifo por camada, não um ícone: o documento imprime em PDF e viaja por
# e-mail, e emoji vira retângulo vazio em metade dos leitores.
GLIFO = {
    'navegador': '▣',
    'servidor': '⬢',
    'fila': '⇶',
    'banco': '▤',
    'externo': '↗',
}


def em_passos(narrativa: list) -> list:
    """Os blocos de `percurso`, em ordem, com a travessia derivada.

    Devolve uma lista de dicionários com `onde`, `texto`, `evidencia`, `saltos`
    e `atravessa` — este último `(de, para)` quando a camada mudou em relação ao
    passo anterior, e `None` no primeiro passo e em quem continua na mesma.
    """
    blocos = sorted((b for b in narrativa if b.get('parte') == 'percurso'),
                    key=lambda b: b.get('ordem', 0))
    passos = []
    anterior = None
    for b in blocos:
        onde = b.get('onde')
        passos.append({
            'onde': onde,
            'texto': b['texto'],
            'evidencia': list(b.get('evidencia') or []),
            'saltos': list(b.get('saltos') or []),
            'atravessa': (anterior, onde) if anterior and onde != anterior else None,
        })
        anterior = onde
    return passos


def travessias(passos: list) -> int:
    """Quantas fronteiras o percurso atravessa. Vai no subtítulo do bloco."""
    return sum(1 for p in passos if p['atravessa'])


def camadas_usadas(passos: list) -> list:
    """As camadas que aparecem, na ordem canônica — não na de aparição.

    Contar as DISTINTAS e não os passos é o que faz o subtítulo dizer algo que o
    leitor não teria contando sozinho: oito passos em duas camadas é um sistema;
    oito em cinco é outro.
    """
    vistas = {p['onde'] for p in passos if p['onde']}
    return [c for c in CAMADAS if c in vistas]


# ───────────────────── escolher QUAL percurso seguir ─────────────────────
#
# O SKILL.md declarava: *"em 'o projeto todo' de um legado, rastrear é adivinhar
# onde a execução começa — e a skill não detecta entrypoint"*. Ela detecta: a
# seção `superficie` já lista rota, job, comando e migration por convenção de
# caminho. O que faltava era usar isso para PROPOR, em vez de deixar o agente
# escolher no escuro — e escolher errado é caro, porque o percurso é a parte do
# documento que mais custa a escrever.

TETO_CANDIDATOS = 5
# A busca para aqui: é candidato, não inventário. Num projeto real a entrada que
# mais alcança chegava a 55 arquivos, bem abaixo do teto.
TETO_ALCANCE = 400
# Entrada que não alcança NINGUÉM pelo import não é candidata — mas é contada, e
# a contagem é dado: num projeto real eram 17 de 49, e isso mede o tamanho do
# ponto cego (quem despacha por string não aparece no grafo).


def _alcance(inicio: str, sai_de: dict) -> set:
    vistos, fila = {inicio}, [inicio]
    while fila and len(vistos) < TETO_ALCANCE:
        atual = fila.pop(0)
        for alvo in sorted(sai_de.get(atual, ())):
            if alvo not in vistos:
                vistos.add(alvo)
                fila.append(alvo)
    return vistos


def candidatos(inv: dict) -> dict:
    """As entradas que mais exercitam o sistema, para escolher o percurso.

    Ordena pelo número de PAPÉIS distintos que a entrada alcança, não pelo número
    de arquivos: uma entrada que toca `request · service · model · enum · helper`
    é fatia vertical; uma que toca trinta modelos é uma listagem. Empate vai para
    o alcance, e depois para o caminho — mesma entrada, mesma ordem, sempre.

    **O limite é declarado junto com a lista**, porque sem ele o leitor conclui
    que o caminho acaba ali: o grafo para na fronteira da aplicação. Num monorepo
    real, nenhuma das 49 entradas atravessava para outro repositório — a
    travessia é por HTTP, e import nenhum a enxerga.
    """
    from lib.funcionalidades import termo_e_papel

    superficie = inv.get('superficie') or []
    if not superficie:
        return {'candidatos': [], 'entradas': 0, 'entradas_sem_alcance': 0,
                'limite': 'nenhuma entrada foi reconhecida por convenção de caminho'}

    sai_de = {}
    for a in (inv.get('imports') or {}).get('arestas') or []:
        sai_de.setdefault(a['de'], set()).add(a['para'])

    achados, sem_alcance = [], 0
    for item in superficie:
        entrada = item['caminho']
        alcancados = _alcance(entrada, sai_de)
        if len(alcancados) <= 1:
            sem_alcance += 1
            continue
        papeis = sorted({p for c in alcancados
                         if (p := (termo_e_papel(c) or (None, None))[1])})
        achados.append({
            'entrada': entrada,
            'tipo': item.get('tipo'),
            # liga os dois eixos: a entrada que mais exercita o sistema costuma
            # levar o nome de uma das funcionalidades do menu
            'termo': (termo_e_papel(entrada) or (None, None))[0],
            'alcanca': len(alcancados),
            'papeis': papeis,
            'primeiros_passos': sorted(sai_de.get(entrada, ()))[:3],
        })
    achados.sort(key=lambda a: (-len(a['papeis']), -a['alcanca'], a['entrada']))
    return {
        'candidatos': achados[:TETO_CANDIDATOS],
        'entradas': len(superficie),
        'entradas_sem_alcance': sem_alcance,
        'limite': ('o grafo para na fronteira da aplicação: travessia entre '
                   'repositórios é por HTTP, e import nenhum a enxerga'),
    }
