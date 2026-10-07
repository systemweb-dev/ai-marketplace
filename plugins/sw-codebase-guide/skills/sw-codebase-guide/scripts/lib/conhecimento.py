"""O que gente sabe e o código não diz — e que precisa sobreviver à regeração.

Os outros três artefatos são descartáveis por desenho: o inventário se refaz, a
interpretação se reescreve, o documento se regera. Este **não**. Ele é o único
arquivo da skill que ninguém pode apagar sem perder informação, e por isso tem o
formato mais fechado de todos.

O que ele guarda é resposta humana **atribuída e datada**. Isso cria o quinto nível
de confiança: os outros quatro são `fato`, `declarado`, `deducao` e `lacuna`, todos
derivados do repositório; `confirmado` é o único cujo lastro é uma pessoa — e por
isso ele nunca aparece sem o nome dela e a data ao lado.

**A resposta envelhece por evidência, não por cronômetro.** Se alguém respondeu
sobre um arquivo em outubro e o arquivo mudou em dezembro, a resposta é mostrada com
aviso: a pergunta pode ter voltado a valer. É o mesmo princípio do resto da skill —
decidir pelo que foi medido, não pelo que se supõe.
"""
import tomllib
from pathlib import Path

ARQUIVO = 'knowledge.toml'
OBRIGATORIOS = ('sobre', 'pergunta', 'resposta', 'quem', 'quando')


def ler(base) -> list:
    """As respostas, da mais recente para a mais antiga por assunto.

    O arquivo guarda o histórico inteiro — responder de novo acrescenta, não
    sobrescreve —, e quem lê fica com a última de cada par (assunto, pergunta). Sem
    isso, corrigir uma resposta exigiria editar o passado à mão.
    """
    caminho = Path(base) / ARQUIVO
    if not caminho.exists():
        return []
    dados = tomllib.loads(caminho.read_text('utf-8'))
    respostas = []
    for i, bloco in enumerate(dados.get('resposta', []), 1):
        faltando = [c for c in OBRIGATORIOS if not str(bloco.get(c, '')).strip()]
        if faltando:
            raise ValueError(f'{ARQUIVO}, resposta {i}: faltam {", ".join(faltando)}')
        respostas.append(dict(bloco))
    respostas.sort(key=lambda r: r['quando'])
    ultimas = {}
    for r in respostas:
        ultimas[(r['sobre'], r['pergunta'])] = r
    return sorted(ultimas.values(), key=lambda r: (r['sobre'], r['pergunta']))


def envelhecidas(respostas: list, por_arquivo: dict) -> list:
    """Marca a resposta cujo assunto MUDOU depois de ela ter sido dada.

    Invalidação por evidência: "este controller é chamado pelo cron" continua
    valendo enquanto ninguém mexe nele. Mexeu, a resposta vira suspeita — não
    falsa, suspeita —, e o documento diz isso em vez de repetir a frase como se
    nada tivesse acontecido.
    """
    saida = []
    for r in respostas:
        item = por_arquivo.get(r['sobre']) or {}
        mudou = item.get('ultima', '')[:10]
        saida.append({**r, 'mudou_depois': mudou if mudou > r['quando'][:10] else None})
    return saida


def indexar(respostas: list) -> dict:
    """Assunto -> respostas sobre ele, para o emissor consultar sem varrer a lista."""
    por_assunto = {}
    for r in respostas:
        por_assunto.setdefault(r['sobre'], []).append(r)
    return por_assunto
