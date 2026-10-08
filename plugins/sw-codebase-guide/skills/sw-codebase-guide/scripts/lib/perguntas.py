"""As perguntas em aberto, derivadas do que foi medido.

A skill declara que as perguntas em aberto são o entregável de maior valor —
são a pauta da conversa com quem conhece o sistema. Mas até aqui elas eram
**três strings fixas** mais as `lacuna` que o agente escreveu, enquanto o
`julgamento` já tinha medido: um arquivo com 55 dependentes e nenhum teste, um
`.env` versionado, um par que muda junto 38 vezes. Nenhum desses fatos virava
pergunta.

*"O `constants/index.js` tem 55 dependentes, mudou 35 vezes e não tem teste —
quem mexe nele hoje, e como sabe que não quebrou nada?"* é pauta de reunião.
*"Estas pastas ainda são usadas?"* é formulário.

**Três regras que valem para toda pergunta daqui:**

1. **Pergunta sem número medido não entra.** O valor está em chegar com o fato
   na mão; sem ele, é conversa que qualquer um puxaria sem a skill.
2. **Pergunta não afirma.** A guarda `PROIBIDAS` do `montar.py` recusaria, e com
   razão: quem lê de relance guarda a frase e esquece o ponto de interrogação.
   Nenhuma pergunta aqui diz que algo não é usado — ela pergunta o que alcança
   aquilo por fora do import.
3. **A genérica só sai quando não há específica.** Perguntar "estas pastas ainda
   são usadas?" logo abaixo de três perguntas nomeando arquivo e dias parados
   faz o documento parecer formulário.
"""

# Um par que muda junto MUITO e não tem aresta de import entre as duas pontas é
# o acoplamento que o grafo não vê — rota em string, injeção de dependência,
# reflexão, template. O piso é alto de propósito: abaixo dele, "mudaram juntos"
# é coincidência de quem mexe em tudo no mesmo commit.
MIN_JUNTOS_SEM_ARESTA = 10
# Teto por categoria: a seção é pauta de reunião, não inventário. Oito perguntas
# sobre arquivo perigoso é a mesma pergunta oito vezes.
TETO_POR_CATEGORIA = 3


def _linguagem(caminho: str, arvore_por_caminho: dict) -> str | None:
    item = arvore_por_caminho.get(caminho)
    return (item or {}).get('linguagem')


def _sem_aresta(inv: dict, confiaveis: set) -> list:
    """Pares que mudam junto e que o grafo não liga.

    Só vale nas linguagens cuja resolução passou do piso: num grafo pela metade,
    "não há aresta" quer dizer "não medi", e a pergunta nasceria de uma ausência
    que é cegueira da skill, não fato do projeto. Por isso as DUAS pontas
    precisam ser de linguagem medida.
    """
    historia = inv.get('historia') or {}
    pares = historia.get('co_mudanca') or []
    if not pares or not confiaveis:
        return []
    arvore = {a['caminho']: a for a in (inv.get('arvore') or [])}
    ligados = set()
    for a in (inv.get('imports') or {}).get('arestas') or []:
        ligados.add((a['de'], a['para']))
        ligados.add((a['para'], a['de']))
    achados, ja_citados = [], set()
    for par in pares:
        if par['vezes'] < MIN_JUNTOS_SEM_ARESTA:
            continue
        caminhos = par['arquivos']
        if len(caminhos) != 2 or tuple(caminhos) in ligados:
            continue
        # um arquivo por categoria: num projeto real os três primeiros pares
        # eram `Rotas` + `Middleware`, `Controller` + `Rotas` e `Controller` +
        # `Middleware` — a mesma pergunta escrita três vezes
        if ja_citados.intersection(caminhos):
            continue
        linguas = {_linguagem(c, arvore) for c in caminhos}
        if None in linguas or not linguas <= confiaveis:
            continue
        ja_citados.update(caminhos)
        achados.append({
            'pergunta': (f'`{caminhos[0]}` e `{caminhos[1]}` mudaram juntos '
                         f'{par["vezes"]} vezes, e nenhum importa o outro. '
                         f'O que liga os dois?'),
            'porque': ('o grafo de import não vê rota em string, injeção de '
                       'dependência, reflexão nem template — e o histórico vê'),
            'evidencia': list(caminhos),
        })
    return achados[:TETO_POR_CATEGORIA]


def _perigosos(inv: dict) -> list:
    achados = []
    for item in ((inv.get('julgamento') or {}).get('perigo') or []):
        achados.append({
            'pergunta': (f'`{item["caminho"]}` tem {item["dependentes"]} '
                         f'dependentes e mudou {item["mudancas"]} vezes. Quem '
                         f'mexe nele hoje, e como essa pessoa sabe que não '
                         f'quebrou nada?'),
            'porque': 'é onde o erro alcança mais gente, e o que mais muda',
            'evidencia': [item['caminho']],
        })
    return achados[:TETO_POR_CATEGORIA]


def _parados(inv: dict) -> list:
    """O que o grafo não alcança e ninguém toca.

    A frase é deliberadamente uma pergunta sobre o que chama o arquivo POR FORA
    do import — nunca uma afirmação de que nada o chama. Essa é a primeira das
    cinco cegueiras que o documento declara.
    """
    achados = []
    for item in ((inv.get('julgamento') or {}).get('sem_alcance') or []):
        achados.append({
            'pergunta': (f'Nenhum import alcança `{item["caminho"]}`, e ele está '
                         f'parado há {item["dias_parado"]} dias. Alguma coisa o '
                         f'chama por fora do import — rota, agendador, '
                         f'framework?'),
            'porque': 'se nada o chamar, é o candidato mais barato a sair',
            'evidencia': [item['caminho']],
        })
    return achados[:TETO_POR_CATEGORIA]


def _risco(inv: dict) -> list:
    """Credencial versionada vira UMA pergunta, não uma por arquivo.

    Três linhas quase iguais empurram para baixo as outras perguntas, e a
    resposta é a mesma para os três.
    """
    versionados = [r['onde'] for r in ((inv.get('julgamento') or {}).get('risco') or [])
                   if r.get('tipo') == 'env-versionado']
    if not versionados:
        return []
    quais = ', '.join(f'`{c}`' for c in sorted(versionados)[:3])
    resto = f' e mais {len(versionados) - 3}' if len(versionados) > 3 else ''
    return [{
        'pergunta': (f'{quais}{resto} {"está" if len(versionados) == 1 else "estão"} '
                     f'no controle de versão. As credenciais que passaram por '
                     f'{"ele" if len(versionados) == 1 else "eles"} foram trocadas?'),
        'porque': 'o que entrou no histórico do git continua lá depois de apagado',
        'evidencia': sorted(versionados),
    }]


def _autoria(inv: dict) -> list:
    """Uma pessoa só, ou projeto parado: muda o risco de assumir o código."""
    retrato = inv.get('retrato') or {}
    autores, commits = retrato.get('autores'), retrato.get('commits')
    if not autores or not commits:
        return []
    if autores > 1:
        return []
    return [{
        'pergunta': (f'Uma pessoa só fez os {commits} commits deste projeto. '
                     f'Ela ainda está por perto para explicar as decisões?'),
        'porque': 'sem segunda fonte, o porquê das decisões não está em lugar nenhum',
        'evidencia': [],
    }]


def _resolucao_fraca(inv: dict, confiaveis: set) -> list:
    """Linguagem cujo grafo ficou abaixo do piso: a skill não vai afirmar nada
    sobre ela, e quem conhece o projeto resolve em uma frase."""
    achados = []
    for ling, c in sorted(((inv.get('imports') or {}).get('resolucao') or {}).items()):
        resolvidos = (c['relativos'] + c['sufixo_unico'] + c['base_provada']
                      + c['config_conferida'])
        denominador = resolvidos + c['ambiguos'] + c['pendurados'] + c['nao_resolvidos']
        if not denominador or ling in confiaveis:
            continue
        achados.append({
            'pergunta': (f'A resolução de imports em `{ling}` ficou em '
                         f'{round(100 * resolvidos / denominador)}%, abaixo do '
                         f'piso. Onde moram os apelidos de caminho desse projeto?'),
            'porque': 'abaixo do piso a skill não afirma dependência nenhuma nessa linguagem',
            'evidencia': [],
        })
    return achados[:TETO_POR_CATEGORIA]


def derivar(inv: dict, confiaveis: set) -> list:
    """Todas as perguntas que os números sustentam, na ordem em que se pergunta.

    A ordem é de urgência, não de categoria: credencial exposta antes de arquivo
    perigoso, arquivo perigoso antes de arquivo parado.
    """
    return (_risco(inv)
            + _perigosos(inv)
            + _sem_aresta(inv, confiaveis)
            + _parados(inv)
            + _autoria(inv)
            + _resolucao_fraca(inv, confiaveis))
