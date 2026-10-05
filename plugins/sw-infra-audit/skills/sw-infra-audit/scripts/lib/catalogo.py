"""Carrega os arquivos de família de exporter — o conhecimento de produto que NÃO vira código.

Mesmo protocolo não significa mesmo esquema: o Traefik publica `traefik_service_requests_total`
com a etiqueta `code`; uma aplicação instrumentada publica `http_requests_total` com `status`.
Um `if produto == ...` dentro do adaptador resolveria hoje e apodreceria amanhã; um arquivo por
família mantém o núcleo agnóstico e faz "adicionar o Kafka" ser escrever um arquivo.

A validação é dura de propósito e acontece no CARREGAMENTO, não na coleta: arquivo que cita
pergunta inexistente, interpolação fora das duas permitidas ou lista sem desempate é recusado
no teste, não no relatório de quem usa.
"""
import re
import tomllib
from pathlib import Path

INTERPOLACOES = ("%SELETOR%", "%JANELA%")
VALORES = ("inteiro", "decimal", "texto")
PASTA = Path(__file__).resolve().parent.parent.parent / "references" / "metricas"
_MARCA = re.compile(r"%[A-Z_]+%")


class CatalogoInvalido(Exception):
    """Arquivo de família que a skill se recusa a interpretar."""


def carregar_arquivo(caminho):
    from lib.papel import PAPEIS
    from lib.perguntas import PERGUNTAS

    caminho = Path(caminho)
    try:
        with caminho.open("rb") as arquivo:
            dados = tomllib.load(arquivo)
    except tomllib.TOMLDecodeError as erro:
        raise CatalogoInvalido(f"{caminho.name}: TOML inválido — {erro}") from erro

    for obrigatorio in ("familia", "prioridade", "identificacao"):
        if obrigatorio not in dados:
            raise CatalogoInvalido(f"{caminho.name}: falta {obrigatorio!r}")
    if not dados.get("seletor", {}).get("etiqueta"):
        raise CatalogoInvalido(f"{caminho.name}: falta `[seletor] etiqueta` — sem ela a "
                               f"consulta agregaria o exporter inteiro como se fosse o "
                               f"componente")
    papel = dados.get("papel")
    if not papel:
        raise CatalogoInvalido(f"{caminho.name}: falta `papel` — é ele que diz de que papel "
                               f"esta família fala, e sem isso ela não pode nem responder "
                               f"pergunta nem provar identidade")
    if papel not in PAPEIS:
        raise CatalogoInvalido(f"{caminho.name}: papel {papel!r} não existe; os papéis são "
                               f"{', '.join(PAPEIS)}")
    if not isinstance(dados.get("identifica_papel"), bool):
        raise CatalogoInvalido(
            f"{caminho.name}: falta `identifica_papel` (booleano). `true` quando a série é "
            f"assinatura do produto e prova o papel de quem a publica; `false` quando ela só "
            f"MEDE — o exporter de container mede qualquer container, e a métrica HTTP "
            f"genérica mede qualquer coisa que fale HTTP. Deixar implícito foi o que quase "
            f"fez toda família votar")
    if not dados["identificacao"].get("metrica_presente"):
        raise CatalogoInvalido(f"{caminho.name}: identificacao sem `metrica_presente` — é ela "
                               f"que diz se esta família é a certa para o componente")

    for pergunta in dados.get("pergunta", []):
        id_ = pergunta.get("id")
        if id_ not in PERGUNTAS:
            raise CatalogoInvalido(f"{caminho.name}: pergunta {id_!r} não existe no registro "
                                   f"de perguntas canônicas")
        if str(id_).split(".")[0] != papel:
            raise CatalogoInvalido(f"{caminho.name}: a família diz falar de {papel!r} e "
                                   f"responde {id_!r}, que é de outro papel — uma das duas "
                                   f"afirmações mente, e descobrir qual no relatório é tarde")
        campos = pergunta.get("campo") or []
        if pergunta.get("query") and campos:
            raise CatalogoInvalido(f"{caminho.name}: {id_} declara `query` e `campo` ao mesmo "
                                   f"tempo — duas fontes para o mesmo item, e nada no arquivo "
                                   f"diz qual vale")
        if not pergunta.get("query") and not campos:
            raise CatalogoInvalido(f"{caminho.name}: {id_} não declara nem `query` nem `campo` "
                                   f"— a família afirma responder algo que não sabe medir")
        for consulta in [pergunta.get("query", "")] + [c.get("query", "") for c in campos]:
            for marca in sorted(set(_MARCA.findall(consulta)) - set(INTERPOLACOES)):
                raise CatalogoInvalido(f"{caminho.name}: interpolação {marca} não é permitida "
                                       f"em {id_}; só {' e '.join(INTERPOLACOES)}")
        if pergunta.get("valor", "inteiro") not in VALORES:
            raise CatalogoInvalido(f"{caminho.name}: valor {pergunta.get('valor')!r} em {id_} "
                                   f"não existe; os tipos são {', '.join(VALORES)}")
        if PERGUNTAS[id_]["forma"] == "lista" and not pergunta.get("desempate"):
            raise CatalogoInvalido(f"{caminho.name}: {id_} é lista e não declara `desempate` — "
                                   f"empate de valor mudaria o relatório entre rodadas")
        if campos:
            _validar_campos(caminho, id_, pergunta, campos, PERGUNTAS[id_])
    return dados


def _validar_campos(caminho, id_, pergunta, campos, canonica):
    """Uma lista cujos itens têm vários campos — uma consulta por campo, juntas pela `chave`.

    Sem isso, uma família promql devolvia um número por item, e a única pergunta do papel
    `fila` ficava fora do alcance de quem tem o exporter no Prometheus mas não a credencial
    da API de administração.
    """
    if canonica["forma"] != "lista":
        raise CatalogoInvalido(f"{caminho.name}: {id_} não é lista, e vários campos não têm "
                               f"onde caber num valor escalar")
    if not pergunta.get("chave"):
        raise CatalogoInvalido(f"{caminho.name}: {id_} tem vários campos e não declara "
                               f"`chave` — é a etiqueta pela qual as consultas se juntam, e "
                               f"sem ela não há item nenhum")
    vistos = set()
    for campo in campos:
        nome = campo.get("nome")
        if not nome:
            raise CatalogoInvalido(f"{caminho.name}: {id_} tem campo sem `nome`")
        if not campo.get("query"):
            raise CatalogoInvalido(f"{caminho.name}: campo `{nome}` de {id_} está sem `query`")
        if nome in vistos:
            raise CatalogoInvalido(f"{caminho.name}: campo `{nome}` aparece duas vezes em "
                                   f"{id_} — o segundo sobrescreveria o primeiro na junção, e "
                                   f"o arquivo pareceria medir duas coisas medindo uma")
        vistos.add(nome)

    # A ordenação é declarada, nunca posicional: com um campo só, "do maior para o menor"
    # não tem ambiguidade; com três, ordenar pelo primeiro bloco do arquivo faria a ordem do
    # relatório depender de onde o autor colou o bloco.
    conhecidos = vistos | {"nome"}
    ordenar = pergunta.get("ordenar_por")
    if not ordenar:
        raise CatalogoInvalido(f"{caminho.name}: {id_} tem vários campos e não declara "
                               f"`ordenar_por` — a ordem viria da posição dos blocos no "
                               f"arquivo, e mexer neles mudaria o topo do relatório")
    if ordenar not in vistos:
        raise CatalogoInvalido(f"{caminho.name}: {id_} ordena por `{ordenar}`, que esta "
                               f"família não mede; os campos são {', '.join(sorted(vistos))}")
    if pergunta["desempate"] not in conhecidos:
        raise CatalogoInvalido(f"{caminho.name}: {id_} desempata por "
                               f"`{pergunta['desempate']}`, que não existe no item — o empate "
                               f"cairia em None e voltaria a herdar a ordem da fonte")

    # A trava que importa: o limiar compara campos, e campo que ninguém mede vale None.
    # `_comparar` devolve False para None por desenho — então o achado que a pergunta existe
    # para produzir simplesmente nunca nasceria, com a suíte toda verde.
    regra = canonica.get("limiar")
    if regra:
        from lib import limiar as _limiar
        faltando = sorted(_limiar.campos(regra["quando"]) - vistos)
        if faltando:
            raise CatalogoInvalido(
                f"{caminho.name}: {id_} carrega o limiar {regra['quando']!r} e esta família "
                f"não mede {', '.join(faltando)} — o achado `{regra['regra']}` nunca "
                f"dispararia, e nada no relatório diria por quê")


def familias(pasta=PASTA):
    """Todas as famílias, em ordem estável: prioridade, depois nome.

    Ordem estável importa: é ela que decide quem responde quando duas famílias identificam o
    mesmo componente, e isso não pode depender da ordem do sistema de arquivos.
    """
    carregadas = [carregar_arquivo(p) for p in sorted(Path(pasta).glob("*.toml"))]
    return sorted(carregadas, key=lambda f: (f["prioridade"], f["familia"]))
