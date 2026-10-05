"""Quem é cada componente, a partir de quem está publicando na fonte.

Este módulo é o ÚNICO lugar da skill que casa nome de componente com valor de etiqueta. Ele é
puro: não abre socket, não importa adaptador. Quem fala com a fonte é o adaptador, por
`reconhecer()`; aqui só se decide o que aquilo significa.

A inversão que ele implementa: em vez de `imagem → kind → papel → filtra famílias → pergunta`,
o caminho passa a ser `fonte → quem publica lá → casa com os componentes → papel → pergunta`.
É o mesmo princípio que o catálogo de métrica já aplica — a série que existe vence o nome.
"""


def casar_valor_da_etiqueta(componente, valores):
    """Qual dos valores que a etiqueta TEM corresponde a este componente — ou None.

    Supor que o valor é o nome do serviço só acerta quando os dois coincidem: verdade para o
    cAdvisor, cujo rótulo É o nome do serviço no Swarm, e quase nunca verdade para `job`, que
    vale o que o scrape config do Prometheus disser. Errando, a consulta caía para o exporter
    inteiro e dois componentes diferentes recebiam o MESMO número.

    A comparação é deliberadamente estreita. Casa por igualdade, e depois só quando um lado é
    o outro com um prefixo separado por `_`, `-` ou `.` — que é como o Swarm nomeia
    (`<stack>_<serviço>`). NÃO casa por substring solta: `db` dentro de `mariadb` atribuiria a
    medida do banco errado, e errar em silêncio é pior que não medir.

    Empate entre dois candidatos igualmente plausíveis devolve None: escolher um seria
    atribuir a medida a quem pode não ser o dono dela.
    """
    if not componente or not valores:
        return None
    if componente in valores:
        return componente

    def nucleo(nome):
        """O último segmento depois de um separador de composição."""
        for sep in ("_", "-", "."):
            if sep in nome:
                nome = nome.rsplit(sep, 1)[-1]
        return nome

    alvo = nucleo(componente)
    candidatos = [v for v in valores if v == alvo or nucleo(v) == alvo or nucleo(v) == componente]
    if len(candidatos) == 1:
        return candidatos[0]
    return None                       # nenhum, ou ambíguo: não atribuir é mais honesto


def base_da_fonte(url):
    """A raiz da API, igual ao que `promql.base_de` faz — a chave de `reconhecido_por_fonte`.

    Pública de propósito: `collect.identificar` agrupa as fontes por ela, e nome privado usado
    entre módulos é contrato por acidente.
    """
    return str(url or "").split("/api/")[0].split("/metrics")[0].rstrip("/")


def resolver(componentes, reconhecido_por_fonte):
    """Papel, origem e as famílias que cobrem cada componente.

    Pura: recebe o que as fontes responderam e devolve o que aquilo significa. A precedência
    está em D2 do spec — `declarado` > `exporter <família>` > `imagem` > `padrão`.

    Uma família só VOTA no papel quando declara `identifica_papel = true` e o componente não é
    um exportador. As duas travas existem pelo mesmo motivo, em direções opostas: o cAdvisor
    casa todo componente (a etiqueta dele É o nome do serviço), e o container de um exporter
    casa a própria família (o núcleo de `<stack>_pg-exporter` e de `pg-exporter` é o mesmo).
    Sem elas o papel sai universalmente `app`, ou sai invertido — o exporter vira o produto.
    """
    saida = {}
    for componente in componentes:
        nome = componente.get("nome")
        familias, votos, soma = [], [], []
        fonte = base_da_fonte(componente.get("metricas_url"))
        for reconhecida in reconhecido_por_fonte.get(fonte, []):
            valores = reconhecida.get("valores") or []
            valor = casar_valor_da_etiqueta(nome, valores)
            if valor is not None:
                etiqueta = reconhecida["seletor"]["etiqueta"]
                familias.append({"familia": reconhecida, "seletor": f'{etiqueta}="{valor}"'})
                if reconhecida.get("identifica_papel") and not componente.get("exportador"):
                    votos.append(reconhecida)
            elif len(set(valores)) == 1:
                # UM valor só: o exporter cobre um componente e o número sem filtro é dele. A
                # fonte carimba `(exporter inteiro)` para quem lê saber de onde veio.
                familias.append({"familia": reconhecida, "seletor": ""})
            elif valores:
                # Vários valores e nenhum casa: o número sem filtro é a SOMA de todos, e
                # entregá-lo como se fosse de um é a mentira que a v0.14.0 consertou. A família
                # NÃO entra no conjunto; o motivo sai por `motivo_da_falta`.
                soma.append(reconhecida)

        papel = componente.get("papel")
        origem = componente.get("papel_origem")
        ambiguidade = []
        if origem != "declarado":
            if len(votos) == 1:
                papel = votos[0]["papel"]
                origem = f"exporter {votos[0]['familia']}"
            elif len(votos) > 1:
                # Carimbar um palpite de autoridade é pior que não carimbar.
                ambiguidade = sorted(v["familia"] for v in votos)

        saida[nome] = {"papel": papel, "papel_origem": origem, "familias": familias,
                       "ambiguidade": ambiguidade,
                       "soma_de_todos": sorted(soma, key=lambda f: f["familia"]),
                       # D3 quer "confirmado pelo exporter; a imagem sugeria banco": quem
                       # sobrescreve o papel devolve o que havia antes, senão o relatório não
                       # tem como dizer isso.
                       "papel_anterior": componente.get("papel")}
    return saida


def familia_da_pergunta(resolvido, pergunta):
    """Qual das famílias que cobrem o componente responde ESTA pergunta — ou None.

    Duas famílias casadas podem declarar o mesmo id: `postgres-exporter` e `mysqld-exporter`
    declaram ambos `banco.conexoes`, e `traefik` e `http-generico` declaram os mesmos
    `entrada.*`. A ordem das chaves é a regra:

    1. seletor CASADO vence seletor vazio. Sem isto, um Postgres que casou a própria etiqueta
       receberia o total do exporter de MySQL — os dois provam papel e têm a MESMA
       `prioridade = 40`, então o desempate cairia no nome, e `mysqld` vem antes;
    2. quem prova papel vence quem só mede;
    3. a `prioridade` do catálogo, que é o critério que já existia.
    """
    candidatas = [f for f in resolvido.get("familias") or []
                  if any(p["id"] == pergunta for p in f["familia"].get("pergunta", []))]
    if not candidatas:
        return None
    return min(candidatas, key=lambda f: (not f["seletor"],
                                          not f["familia"].get("identifica_papel"),
                                          f["familia"].get("prioridade", 99),
                                          f["familia"]["familia"]))


def motivo_da_falta(resolvido, pergunta):
    """Por que esta pergunta não tem família — na linguagem que manda o dono ao lugar certo.

    Antes este motivo nascia dentro do adaptador, a partir do estado `seletor = None` que o
    passe eliminou. Produzi-lo aqui mantém uma decisão num lugar só, e preserva a distinção que
    importa: "não reconheci a família deste componente" manda procurar exporter; "o número sem
    filtro seria a soma de todos" manda olhar a etiqueta do scrape.
    """
    if not resolvido:
        return None
    for familia in resolvido.get("soma_de_todos") or []:
        # Só a família que DECLARA esta pergunta produz o motivo. Sem esta checagem, um
        # componente medido pelo exporter de container e com um proxy na soma recebia "o
        # exporter traefik cobre vários componentes" para `app.cpu` — pergunta que o traefik
        # nem conhece. O motivo certo ali é o fallback de quem chama, "não reconheci a
        # família", e trocá-lo manda o dono para o lugar errado, em escala.
        if any(p["id"] == pergunta for p in familia.get("pergunta", [])):
            return (f"o exporter {familia['familia']} cobre vários componentes e nenhum valor "
                    f"da etiqueta casa com este — o número sem filtro seria a soma de todos")
    return None
