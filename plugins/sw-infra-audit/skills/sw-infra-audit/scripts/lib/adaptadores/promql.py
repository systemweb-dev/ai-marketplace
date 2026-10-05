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
# `casar_valor_da_etiqueta` mudou de casa: ela é identificação, não consulta, e o
# módulo `identificacao` é o único lugar que casa nome de componente com valor de
# etiqueta. Reexportada aqui porque o nome já era importado deste módulo.
from lib.identificacao import base_da_fonte, casar_valor_da_etiqueta  # noqa: F401

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

    Delega para `identificacao.base_da_fonte`: era a MESMA expressão escrita duas vezes, e o
    passe agrupa as fontes por aquela — duas cópias de um normalizador derivam, e aí um
    componente é agrupado numa fonte e consultado noutra.

    O `configurar.py alvos --sugerir` imprime a URL completa de uma consulta, e é natural colar
    aquilo inteiro. Sem normalizar, viraria `.../api/v1/query?query=up/api/v1/query` → 404 →
    "a fonte não respondeu", que manda o dono caçar problema de rede que não existe.
    """
    return base_da_fonte(url)


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


def _valores_da_etiqueta(base, familia, contexto):
    """Os valores que a etiqueta da família realmente tem nesta fonte."""
    serie = familia["identificacao"]["metrica_presente"]
    etiqueta = familia["seletor"]["etiqueta"]
    bruto = _consultar(base, f"count by ({etiqueta}) ({serie})", contexto["timeout"],
                       contexto.get("at"))
    if not bruto:
        return []
    return [str(((r.get("metric") or {}).get(etiqueta) or "")) for r in bruto if r]


def reconhecer(fonte, contexto):
    """Quem está publicando nesta fonte. UMA consulta por família, nunca por componente.

    É o contrato que o passe de identificação consome. A consulta de descoberta depende só de
    (fonte, família) — por isso o resultado fica no cache COMPARTILHADO do alvo
    (`contexto["cache"]`, criado em `collect.py`), e não numa cópia por pergunta, que era onde
    o cache anterior morria: a mesma identificação rodava uma vez por pergunta.
    """
    base = base_de(fonte)
    cache = contexto.setdefault("cache", {}).setdefault("reconhecido", {})
    if base in cache:
        return cache[base]

    saida = []
    for familia in catalogo.familias():
        valores = _valores_da_etiqueta(base, familia, contexto)
        if valores:
            saida.append(dict(familia, valores=valores))
    cache[base] = saida
    return saida


def familia_do_componente(componente, contexto, pergunta):
    """(família, seletor) para ESTA pergunta — ou (None, None).

    Não identifica mais nada: quem identifica é o passe (`collect.identificar`), e este módulo
    só consulta o resultado. Foi assim que a decisão de papel deixou de ser efeito colateral de
    uma chamada de adaptador, e que o filtro por papel da v0.14.0 pôde sair — a proteção que ele
    dava passou a ser `identifica_papel` mais o casamento de etiqueta, que são evidência e não
    heurística.

    A `pergunta` entrou na assinatura porque, sem o filtro, duas famílias casadas podem declarar
    o MESMO id: o desempate vive em `identificacao.familia_da_pergunta`.
    """
    from lib import identificacao

    resolvido = contexto.get("cache", {}).get("resolvido", {}).get(componente.get("nome"))
    escolhida = identificacao.familia_da_pergunta(resolvido or {}, pergunta)
    if escolhida is None:
        return (None, None)
    return (escolhida["familia"], escolhida["seletor"])


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

    from lib import identificacao

    base = base_de(base)
    familia, seletor = familia_do_componente(componente, contexto, pergunta)
    if familia is None:
        # A alcançabilidade vem do CACHE do passe, não de uma sonda nova. Sondar aqui rodava uma
        # vez por pergunta para todo componente não resolvido, e é a segunda das duas chamadas
        # que a restrição nº 1 manda tirar para o teto `K×(F+1)` valer.
        cache = contexto.get("cache", {})
        if cache.get("fonte_viva", {}).get(base) is False:
            return _sem_dados(pergunta, "a fonte de métrica não respondeu")
        resolvido = cache.get("resolvido", {}).get(componente.get("nome")) or {}
        motivo = identificacao.motivo_da_falta(resolvido, pergunta)
        if not motivo and resolvido.get("familias"):
            # A família FOI reconhecida; ela é que não publica este dado. Dizer "não reconheci
            # a família" aqui manda o dono procurar exporter que já existe — degradação de
            # motivo em escala, que é o que o passe não pode introduzir.
            nomes = ", ".join(sorted({f["familia"]["familia"]
                                      for f in resolvido["familias"]}))
            motivo = f"o exporter {nomes} não expõe o dado desta pergunta"
        return _sem_dados(pergunta, motivo or "a fonte respondeu, mas não reconheci a família "
                                              "de métrica deste componente")

    # `familia_da_pergunta` só devolve família que DECLARA a pergunta, então o ramo antigo de
    # "não expõe o dado desta pergunta" aqui virou inalcançável — ele vive agora no ramo
    # `familia is None` acima, que é onde o caso realmente cai.
    declarada = next(p for p in familia["pergunta"] if p["id"] == pergunta)

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
