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


def _seletor(familia, componente):
    """`job="proxy"` — a etiqueta declarada pela família, com o nome do componente."""
    return f'{familia["seletor"]["etiqueta"]}="{componente["nome"]}"'


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
    for familia in catalogo.familias():
        serie = familia["identificacao"]["metrica_presente"]
        seletor = _seletor(familia, componente)
        if _consultar(base, f"count({serie}{{{seletor}}})", contexto["timeout"],
                      contexto.get("at")):
            achada = (familia, seletor)
            break
        if _consultar(base, f"count({serie})", contexto["timeout"], contexto.get("at")):
            achada = (familia, "")
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
    if familia is None:
        if not alcancavel(base, contexto):
            return _sem_dados(pergunta, "a fonte de métrica não respondeu")
        return _sem_dados(pergunta, "a fonte respondeu, mas não reconheci a família de métrica "
                                    "deste componente")

    declarada = next((p for p in familia.get("pergunta", []) if p["id"] == pergunta), None)
    if declarada is None:
        return _sem_dados(pergunta,
                          f"o exporter {familia['familia']} não expõe o dado desta pergunta")

    query = (declarada["query"]
             .replace("%SELETOR%", seletor)
             .replace("%JANELA%", str(contexto.get("janela", "24h"))))
    resultado = _consultar(base, query, contexto["timeout"], contexto.get("at"))
    if resultado is None:
        return _sem_dados(pergunta, "a fonte de métrica não respondeu")

    fonte = f"{ID}:{familia['familia']}" + ("" if seletor else " (exporter inteiro)")
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
