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
