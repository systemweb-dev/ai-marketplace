"""Adaptador PromQL — o único que funciona sem credencial, e por isso o primeiro.

Ele não sabe o que é Traefik. Sabe perguntar "que família você é?" olhando qual série existe no
endereço declarado, e a partir daí as consultas vêm do arquivo daquela família. Pergunta que a
família não expõe responde `sem_dados` com o motivo — não se inventa dado a partir de outra
métrica, nem se cai em outra família silenciosamente.

Toda rede passa por `lib/http_get.py`: aqui não se importa urllib nem socket.
"""
import json
import math
from datetime import datetime, timezone
from urllib.parse import quote

from lib import catalogo, http_get

ID = "promql"


def momento(at):
    """O `--at` em segundos de época — é ele que ancora a consulta.

    `/api/v1/query` aceita `time=`; sem isso a janela andaria com o relógio de quem rodou, e
    duas execuções da mesma entrada dariam números diferentes.
    """
    texto = str(at or "").replace("Z", "+00:00")
    try:
        instante = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    return int(instante.timestamp())


def base_de(url):
    """A raiz da API a partir do que o dono colou no alvos.toml.

    O `configurar.py alvos --sugerir` imprime a URL completa de uma consulta, e é natural colar
    aquilo inteiro. Sem normalizar, viraria `.../api/v1/query?query=up/api/v1/query` → 404 →
    "a fonte não respondeu", que manda o dono caçar problema de rede que não existe.
    """
    return str(url or "").split("/api/")[0].split("/metrics")[0].rstrip("/")


def _consultar(base, query, timeout, at=None):
    """Uma consulta instantânea. Devolve a lista de séries, ou None quando não deu para ler."""
    url = f"{base.rstrip('/')}/api/v1/query?query={quote(query)}"
    instante = momento(at)
    if instante is not None:
        url += f"&time={instante}"
    # NotConfirmed NÃO é capturado: destino fora da allowlist é erro de programação, e os
    # outros coletores deixam propagar. Engolir aqui faria bug virar "fonte indisponível".
    codigo, corpo = http_get.get_com_status(url, [http_get.destino(base)], timeout=timeout)
    if codigo != 200 or not corpo:
        return None
    try:
        dados = json.loads(corpo)
    except ValueError:
        return None
    if dados.get("status") != "success":
        return None
    return dados.get("data", {}).get("result", [])


def alcancavel(base, contexto):
    """A fonte responde a uma consulta trivial? Separa "não cheguei lá" de "cheguei e não
    reconheci" — o primeiro é rede ou endereço errado, o segundo é exporter desconhecido."""
    return _consultar(base, "vector(1)", contexto["timeout"], contexto.get("at")) is not None


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


def _valores_da_etiqueta(base, familia, contexto):
    """Os valores que a etiqueta da família realmente tem nesta fonte."""
    serie = familia["identificacao"]["metrica_presente"]
    etiqueta = familia["seletor"]["etiqueta"]
    bruto = _consultar(base, f"count by ({etiqueta}) ({serie})", contexto["timeout"],
                       contexto.get("at"))
    if not bruto:
        return []
    return [str(((r.get("metric") or {}).get(etiqueta) or "")) for r in bruto if r]


def _seletor(familia, componente, valores=None):
    """`job="proxy"` — a etiqueta declarada pela família, com o valor que casa com o
    componente. Sem casamento, devolve vazio: a resposta vira a do exporter inteiro e a
    fonte DIZ isso, em vez de mentir que o número é daquele componente."""
    etiqueta = familia["seletor"]["etiqueta"]
    nome = componente.get("nome") or ""
    valor = casar_valor_da_etiqueta(nome, valores) if valores is not None else nome
    return f'{etiqueta}="{valor}"' if valor else ""


def familia_do_componente(componente, contexto):
    """(família, seletor) — ou (None, None) quando ninguém reconhece este componente.

    A identificação é ESCOPADA pelo componente: `count(serie{job="x"})` em vez de
    `count(serie)`. Sem escopo, a pergunta vira "este Prometheus tem alguma série de Traefik?",
    e aí TODO componente que aponte para o mesmo Prometheus — inclusive o banco — viraria
    Traefik.

    Se a série existe mas não com esse escopo, cai para o exporter inteiro e DIZ isso na fonte:
    num cluster com um proxy só, o número sem filtro é a resposta certa; mentir que ele é do
    componente é que não pode.

    O resultado fica em cache no contexto do alvo: são duas consultas por família, e repetir
    isso a cada pergunta multiplicaria o tráfego por nada.
    """
    base = base_de(componente.get("metricas_url"))
    cache = contexto.setdefault("_familia_por_base", {})
    chave = (base, componente.get("nome"))
    if chave in cache:
        return cache[chave]

    achada = (None, None)
    papel = componente.get("papel")
    for familia in catalogo.familias():
        # A família só é candidata se responde alguma pergunta DO PAPEL deste componente.
        # Sem este filtro, um `banco` apontando para o mesmo Prometheus seria identificado
        # como Traefik — a série existe naquele Prometheus, afinal — e receberia o número do
        # exporter inteiro como se fosse dele. O prefixo do id da pergunta (`entrada.`,
        # `app.`) é o que liga família a papel, sem nenhum nome de produto no código.
        if not any(str(q["id"]).split(".")[0] == papel for q in familia.get("pergunta", [])):
            continue
        serie = familia["identificacao"]["metrica_presente"]
        # Descobrir os valores que a etiqueta TEM, em vez de supor que ela vale o nome do
        # serviço no Swarm. Esta consulta é o que separa "a medida é deste componente" de
        # "a medida é do exporter inteiro" — e a suposição antiga fazia dois componentes
        # diferentes receberem o MESMO número, com a fonte dizendo que era de cada um.
        valores = _valores_da_etiqueta(base, familia, contexto)
        if not valores:
            continue
        seletor = _seletor(familia, componente, valores)
        if seletor and _consultar(base, f"count({serie}{{{seletor}}})",
                                  contexto["timeout"], contexto.get("at")):
            achada = (familia, seletor)
            break
        # A família é esta, mas nenhum valor casou com o componente. Com UM valor só, o
        # exporter cobre um componente e o número sem filtro é dele — a fonte carimba
        # "exporter inteiro" para quem lê saber de onde veio. Com vários, o número sem
        # filtro é a SOMA de todos, e entregá-lo como se fosse de um era exatamente a
        # mentira que fazia dois componentes exibirem a mesma medida.
        achada = (familia, "" if len(set(valores)) == 1 else None)
        break
    cache[chave] = achada
    return achada


def _converter(bruto, tipo):
    """None quando o valor não é número.

    `histogram_quantile` sem amostras devolve NaN, e NaN escrito no report.json produz JSON
    INVÁLIDO para qualquer leitor fora do Python. Valor que não é número não é valor.
    """
    try:
        numero = float(bruto)
    except (TypeError, ValueError):
        return None
    if math.isnan(numero) or math.isinf(numero):
        return None
    return int(numero) if tipo == "inteiro" else round(numero, 2)


def _sem_dados(pergunta, motivo):
    return {"pergunta": pergunta, "sem_dados": True, "motivo": motivo}


def _interpolar(query, seletor, contexto):
    return (str(query).replace("%SELETOR%", seletor)
            .replace("%JANELA%", str(contexto.get("janela", "24h"))))


def _lista_de_campos(pergunta, declarada, base, seletor, contexto, fonte):
    """Uma consulta por campo, juntas pela etiqueta de `chave`.

    Uma consulta PromQL devolve um número por série, e por isso uma família só conseguia
    responder `{chave, valor}`. `fila.filas` precisa de três campos, e o limiar que produz
    `fila_sem_consumidor` compara dois deles — o papel `fila` ficava fora do alcance de quem
    tem o exporter no Prometheus e não a credencial da API de administração.

    Campo que a consulta não devolveu para aquele item fica `None`, nunca 0: preencher com
    zero produziria `fila_sem_consumidor` em cima de uma medida que ninguém fez, e `None` é o
    que o limiar sabe recusar.
    """
    etiqueta = declarada["chave"]
    tipo = declarada.get("valor", "inteiro")
    nomes = [campo["nome"] for campo in declarada["campo"]]
    itens = {}
    respondeu = series = False
    for campo in declarada["campo"]:
        resultado = _consultar(base, _interpolar(campo["query"], seletor, contexto),
                               contexto["timeout"], contexto.get("at"))
        if resultado is None:
            continue
        respondeu = True
        series = series or bool(resultado)
        for linha in resultado:
            chave = str((linha.get("metric") or {}).get(etiqueta, ""))
            if not chave:
                continue
            itens.setdefault(chave, {})[campo["nome"]] = _converter(linha["value"][1], tipo)

    if not respondeu:
        return _sem_dados(pergunta, "a fonte de métrica não respondeu")
    if not itens:
        # Lista vazia diria "não há fila"; `sem dados` diz "não consegui ver". A primeira sai
        # no relatório como componente saudável, que é a mentira mais cara que ele comete.
        if series:
            # Série existe, mas sem a etiqueta de junção. É o caso do exporter configurado
            # para AGREGAR — e o motivo genérico ("nada respondeu") mandaria o dono caçar
            # problema de rede quando o conserto é uma chave de configuração do exporter.
            return _sem_dados(pergunta, f"as consultas responderam, mas nenhuma série traz a "
                                        f"etiqueta `{etiqueta}` — o exporter está publicando "
                                        f"a métrica agregada, sem separar por objeto")
        return _sem_dados(pergunta, "nenhuma das consultas desta família devolveu série")

    montados = [dict({"nome": chave}, **{nome: medidos.get(nome) for nome in nomes})
                for chave, medidos in itens.items()]
    ordem, desempate = declarada["ordenar_por"], declarada["desempate"]
    # do maior para o menor pelo campo DECLARADO; empate pelo campo de identidade, nunca pela
    # ordem da resposta — que é o que faria o topo mudar entre rodadas sem nada ter mudado.
    montados.sort(key=lambda item: (-(item.get(ordem) or 0), str(item.get(desempate) or "")))
    return {"pergunta": pergunta, "fonte": fonte, "valor": montados}


def perguntar(pergunta, componente, contexto):
    """Responde a pergunta, ou devolve `sem_dados` com o motivo real."""
    base = componente.get("metricas_url")
    if not base:
        if not any(p.get("id") == pergunta for familia in catalogo.familias()
                   for p in familia.get("pergunta", [])):
            # Nenhuma família do catálogo sabe responder isto. Pedir `metricas_url` aqui
            # mandaria o dono configurar algo que não faz a pergunta responder — era o que
            # acontecia com todo componente de `fila` antes de existir o adaptador de API.
            # Com `metricas_url` declarado, o caminho normal dá o motivo mais específico
            # ("o exporter X não expõe..."), então esta checagem fica só neste ramo.
            return dict(_sem_dados(pergunta, "nenhuma família de exporter conhecida "
                                             "responde a esta pergunta"), nao_se_aplica=True)
        return _sem_dados(pergunta, "o componente não declara `metricas_url` no alvos.toml")

    base = base_de(base)
    familia, seletor = familia_do_componente(componente, contexto)
    if familia is not None and seletor is None:
        etiqueta = familia["seletor"]["etiqueta"]
        return _sem_dados(pergunta, f"o exporter {familia['familia']} cobre vários componentes "
                                    f"e nenhum valor de `{etiqueta}` casa com este — o número "
                                    f"sem filtro seria a soma de todos")
    if familia is None:
        if not alcancavel(base, contexto):
            return _sem_dados(pergunta, "a fonte de métrica não respondeu")
        return _sem_dados(pergunta, "a fonte respondeu, mas não reconheci a família de métrica "
                                    "deste componente")

    declarada = next((p for p in familia.get("pergunta", []) if p["id"] == pergunta), None)
    if declarada is None:
        return _sem_dados(pergunta,
                          f"o exporter {familia['familia']} não expõe o dado desta pergunta")

    fonte = f"{ID}:{familia['familia']}" + ("" if seletor else " (exporter inteiro)")
    if declarada.get("campo"):
        return _lista_de_campos(pergunta, declarada, base, seletor, contexto, fonte)

    query = (_interpolar(declarada["query"], seletor, contexto))
    resultado = _consultar(base, query, contexto["timeout"], contexto.get("at"))
    if resultado is None:
        return _sem_dados(pergunta, "a fonte de métrica não respondeu")

    tipo = declarada.get("valor", "inteiro")
    chave = declarada.get("chave")
    if chave:
        itens = [{"chave": str(linha.get("metric", {}).get(chave, "")),
                  "valor": _converter(linha["value"][1], tipo)} for linha in resultado]
        itens = [item for item in itens if item["valor"] is not None]
        # do maior para o menor; empate resolve pela chave — nunca pela ordem da resposta,
        # que é o que faria o top N mudar entre rodadas sem nada ter mudado na infraestrutura
        itens.sort(key=lambda item: (-item["valor"], item["chave"]))
        return {"pergunta": pergunta, "fonte": fonte, "valor": itens}

    if not resultado:
        return _sem_dados(pergunta, "a consulta não devolveu série")
    if len(resultado) > 1:
        # escalar com várias séries significa seletor frouxo: escolher uma seria inventar
        return _sem_dados(pergunta, f"a consulta devolveu {len(resultado)} séries onde se "
                                    f"esperava uma — o seletor não distingue este componente")
    valor = _converter(resultado[0]["value"][1], tipo)
    if valor is None:
        return _sem_dados(pergunta, "a fonte devolveu um valor que não é número (sem amostras "
                                    "na janela)")
    return {"pergunta": pergunta, "fonte": fonte, "valor": valor}
