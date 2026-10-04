"""Perguntas canônicas para os papéis que ficavam mudos.

Numa rodada real, 54 de 57 componentes não recebiam pergunta nenhuma — `app` (49), `banco`,
`cache` e `observabilidade`. O relatório os inventariava e não os media.

A disciplina do arquivo de perguntas vale aqui também, e é o que impede isto de virar
enfeite: só entra o que QUALQUER família daquele papel responde, e `faixa` só quando a
tolerância existe de verdade. Agulha sem tolerância declarada sugere uma leitura que ninguém
definiu.
"""
import pytest

from lib.perguntas import PERGUNTAS, REGRAS_PRODUZIDAS, do_papel


@pytest.mark.parametrize("papel,esperadas", [
    ("app", 2),       # cpu e memória — respondidas pelo exporter de container, não pela app
    ("banco", 2),     # conexões e tamanho
    # taxa de acerto ficou de FORA: a razão entre acertos e erros exige aritmética que a
    # linguagem de extração não tem, e nenhuma família conseguiria respondê-la
    ("cache", 2),     # memória em uso e chaves descartadas
])
def test_papel_passa_a_ter_pergunta(papel, esperadas):
    assert len(do_papel(papel)) == esperadas


def test_as_perguntas_de_app_sao_respondidas_pela_INFRAESTRUTURA():
    """`app` é o papel de 49 componentes heterogêneos: não existe métrica que toda aplicação
    publique. O que existe para qualquer uma é o que o CONTAINER consome — e isso quem
    responde é o exporter de container, não a aplicação."""
    ids = {p["id"] for p in do_papel("app")}

    assert ids == {"app.cpu", "app.memoria"}


def test_nenhuma_pergunta_nova_inventa_faixa():
    """CPU "boa" depende do limite configurado; tamanho de banco depende do negócio; taxa de
    acerto depende da carga. Declarar faixa aqui seria chute com agulha."""
    novas = [p for p in PERGUNTAS.values() if p["papel"] in ("app", "banco", "cache")]

    assert novas, "o teste precisa ter o que verificar"
    assert all(p["faixa"] is None for p in novas)


def test_nenhuma_pergunta_nova_duplica_achado_que_ja_existe():
    """`OPS_TASK_FAILING` já nasce do coletor docker. Uma pergunta com limiar sobre reinício
    produziria o MESMO achado por outro caminho — e contar duas vezes o mesmo problema é o
    defeito que a deduplicação acabou de consertar."""
    from lib.regras import REGRAS

    novas = [p for p in PERGUNTAS.values() if p["papel"] in ("app", "banco", "cache")]

    assert all(p["limiar"] is None for p in novas)
    assert "OPS_TASK_FAILING" not in REGRAS_PRODUZIDAS


def test_toda_pergunta_de_lista_declara_desempate():
    """Empate de valor não pode herdar a ordem da fonte: duas execuções dariam ordens
    diferentes para a mesma entrada."""
    for p in PERGUNTAS.values():
        if p["forma"] == "lista":
            assert p["desempate"], f'{p["id"]} é lista e não declara desempate'


def test_observabilidade_continua_sem_pergunta_de_proposito():
    """Prometheus, Loki e Grafana não compartilham vocabulário de métrica: não existe
    pergunta que QUALQUER família de observabilidade responda. Inventar uma só para o papel
    deixar de aparecer mudo seria preencher a lacuna com ruído."""
    assert do_papel("observabilidade") == []


# ------------------------------------------------- a trava estrutural
def test_toda_pergunta_declarada_tem_alguem_que_a_responda():
    """Pergunta sem família capaz de respondê-la vira `sem dados` permanente: derruba a
    cobertura sem que haja nada a consertar, e ensina quem lê a ignorar o número.

    Eu mesmo escorreguei nisto ao acrescentar `cache.taxa_de_acerto`: a razão entre acertos e
    erros exige aritmética que a linguagem de extração não tem, e nenhum arquivo de família
    conseguia respondê-la. Esta trava é o que impede a próxima.
    """
    import tomllib
    from pathlib import Path

    from lib.catalogo import familias

    raiz = Path(__file__).resolve().parents[1] / "references"
    respondidas = {q["id"] for fam in familias() for q in fam.get("pergunta", [])}
    for arquivo in (raiz / "apis").glob("*.toml"):
        dados = tomllib.loads(arquivo.read_text(encoding="utf-8"))
        respondidas |= {q["id"] for q in dados.get("pergunta", [])}

    orfas = sorted(set(PERGUNTAS) - respondidas)

    assert not orfas, (f"perguntas que nenhuma família responde: {orfas}. "
                       f"Ou escreva o arquivo de família, ou não declare a pergunta.")


def test_toda_pergunta_respondida_por_familia_existe_no_registro():
    """O inverso: família que responde um id que ninguém declarou é consulta que nunca roda,
    e um erro de digitação no catálogo passaria em silêncio."""
    from lib.catalogo import familias

    declaradas = set(PERGUNTAS)
    for fam in familias():
        for q in fam.get("pergunta", []):
            assert q["id"] in declaradas, \
                f'{fam["familia"]} responde {q["id"]!r}, que não existe em perguntas.py'
