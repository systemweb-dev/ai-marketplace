"""Carrega os arquivos de família de API — o conhecimento de produto que NÃO vira código.

Irmão do `lib/catalogo.py` (que serve o `promql`), mas a linguagem é outra: aqui o alvo é JSON
de API de administração, e a linguagem é a de `lib/extracao.py`.

A validação é dura e acontece no CARREGAMENTO. Erro de catálogo que só aparece na coleta vira
"a API não respondeu" no relatório; e o pior tipo de erro de catálogo nem levanta — produz
resposta errada com cara de certa. Por isso este módulo recusa, além do que é inválido, o que
é válido mas mente:

- `caminho` que sai da `admin_url`: é por ele que a CREDENCIAL sai da máquina;
- `limiar` no catálogo: ele pertence à pergunta canônica, e aqui seria letra morta;
- `limite` em pergunta que tem limiar: o limiar veria só a lista cortada, e 300 filas órfãs
  atrás de 10 filas cheias dariam zero achados;
- catálogo que não extrai os campos que o limiar da pergunta compara: a regra morreria calada.
"""
import tomllib
from pathlib import Path

from lib.extracao import ExtracaoInvalida, validar_declaracao

PASTA = Path(__file__).resolve().parent.parent.parent / "references" / "apis"

# A linguagem inteira. Chave fora daqui é erro de digitação — ou uma tentativa de estendê-la em
# silêncio: `filtro = "..."` passaria calado e o autor acharia que filtrou.
CHAVES_DA_PERGUNTA = {"id", "caminho", "lista", "identidade", "campos", "transformar",
                      "derivar", "ordenar_por", "ordem", "desempate", "limite"}


class CatalogoInvalido(Exception):
    """Arquivo de família de API que a skill se recusa a interpretar."""


def _validar_caminho(arquivo, onde, caminho):
    """O caminho é relativo à `admin_url` e não pode sair dela. Nunca."""
    cru = str(caminho or "")
    if not cru.startswith("/"):
        raise CatalogoInvalido(f"{arquivo}: caminho {cru!r} em {onde} precisa começar com '/'")
    if cru.startswith("//") or "://" in cru:
        raise CatalogoInvalido(
            f"{arquivo}: caminho {cru!r} em {onde} aponta para outro host — o caminho é "
            f"relativo à `admin_url` do componente, e é por ele que a credencial sai")
    if ".." in cru.split("/"):
        raise CatalogoInvalido(f"{arquivo}: caminho {cru!r} em {onde} sobe de diretório")


def campos_do_limiar(limiar):
    """Os nomes de campo que a expressão compara — o contrato com o catálogo."""
    from lib.limiar import campos

    return campos((limiar or {}).get("quando"))


def _validar_pergunta(arquivo, pergunta, registro):
    id_ = pergunta.get("id")
    if id_ not in registro:
        raise CatalogoInvalido(
            f"{arquivo}: pergunta {id_!r} não existe no registro de perguntas canônicas")

    desconhecidas = sorted(set(pergunta) - CHAVES_DA_PERGUNTA - {"limiar"})
    if desconhecidas:
        raise CatalogoInvalido(
            f"{arquivo}: {id_} usa {', '.join(desconhecidas)}, que não existe na linguagem "
            f"de extração — o que não cabe nela vira adaptador, não chave nova")
    if "limiar" in pergunta:
        raise CatalogoInvalido(
            f"{arquivo}: {id_} declara `limiar`, mas o limiar pertence à pergunta canônica "
            f"(lib/perguntas.py) e não depende de quem responde. Aqui ele seria ignorado")

    _validar_caminho(arquivo, id_, pergunta.get("caminho"))
    try:
        validar_declaracao(pergunta)
    except ExtracaoInvalida as erro:
        raise CatalogoInvalido(f"{arquivo}: {id_} — {erro}") from erro

    extraidos = set(pergunta.get("campos") or {}) | set(pergunta.get("derivar") or {})

    if registro[id_]["forma"] == "escalar" and ("lista" in pergunta or "valor" not in extraidos):
        # Escalar é UM número: o catálogo diz de onde ele vem num campo `valor`, e o adaptador
        # entrega o número — não o dicionário `{"valor": 17}`, que o limiar e o relatório não
        # sabem ler.
        raise CatalogoInvalido(
            f"{arquivo}: {id_} é escalar — declare o número em `campos = {{ valor = ... }}` e "
            f"sem `lista`")

    identidade = pergunta.get("identidade")
    if identidade is not None:
        if not isinstance(identidade, list) or not identidade:
            raise CatalogoInvalido(
                f"{arquivo}: {id_} — `identidade` precisa ser uma lista não vazia de campos")
        fora = [campo for campo in identidade if campo not in extraidos]
        if fora:
            raise CatalogoInvalido(
                f"{arquivo}: {id_} — `identidade` cita {', '.join(map(repr, fora))}, que não "
                f"está entre os campos extraídos")

    limiar = registro[id_].get("limiar")
    if limiar:
        if pergunta.get("limite") is not None:
            raise CatalogoInvalido(
                f"{arquivo}: {id_} tem limiar na pergunta canônica e declara `limite` — o "
                f"limiar veria só a lista cortada, e o que ficou fora do corte nunca viraria "
                f"achado. O corte para exibição é do relatório")
        faltando = sorted(campos_do_limiar(limiar) - extraidos)
        if faltando:
            raise CatalogoInvalido(
                f"{arquivo}: {id_} não extrai {', '.join(faltando)}, que o limiar da pergunta "
                f"compara — sem ele o campo vira None e a regra nunca dispara")


def carregar_arquivo(caminho):
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

    identificacao = dados["identificacao"]
    _validar_caminho(caminho.name, "identificacao", identificacao.get("caminho"))
    exige = identificacao.get("exige_chaves")
    if not isinstance(exige, list) or not exige:
        raise CatalogoInvalido(
            f"{caminho.name}: identificacao sem `exige_chaves` — sem chave exigida, qualquer "
            f"JSON que responda 200 vira esta família, e a primeira do catálogo responderia "
            f"por todo componente")

    for pergunta in dados.get("pergunta", []):
        _validar_pergunta(caminho.name, pergunta, PERGUNTAS)
    return dados


def familias(pasta=PASTA):
    """Todas as famílias, em ordem estável: prioridade, depois nome.

    Ordem estável decide quem responde quando duas famílias identificam o mesmo componente,
    e isso não pode depender da ordem do sistema de arquivos.
    """
    carregadas = [carregar_arquivo(p) for p in sorted(Path(pasta).glob("*.toml"))]
    return sorted(carregadas, key=lambda f: (f["prioridade"], f["familia"]))
