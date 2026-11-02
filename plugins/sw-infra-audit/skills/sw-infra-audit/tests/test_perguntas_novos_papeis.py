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
    ("app", 3),       # cpu, memória e disponibilidade — do exporter de container, não da app
    ("banco", 2),     # conexões e tamanho
    ("cache", 3),     # memória em uso, chaves descartadas e taxa de acerto, opcional
    ("maquina", 4),   # CPU, memória, disco e dias até encher, todas opcionais
])
def test_papel_passa_a_ter_pergunta(papel, esperadas):
    assert len(do_papel(papel)) == esperadas


def test_as_perguntas_de_app_sao_respondidas_pela_INFRAESTRUTURA():
    """`app` é o papel de 49 componentes heterogêneos: não existe métrica que toda aplicação
    publique. O que existe para qualquer uma é o que o CONTAINER consome — e isso quem
    responde é o exporter de container, não a aplicação."""
    ids = {p["id"] for p in do_papel("app")}

    assert ids == {"app.cpu", "app.memoria", "app.disponibilidade_7d"}


def test_perguntas_novas_sao_opcionais():
    for id_ in ("cache.acerto", "maquina.disco_dias", "app.disponibilidade_7d"):
        assert PERGUNTAS[id_]["forma"] == "escalar" and PERGUNTAS[id_]["opcional"]
    assert PERGUNTAS["app.disponibilidade_7d"]["titulo"] == "Disponibilidade em 7 dias"
    assert "app.disponibilidade_30d" not in PERGUNTAS


def _consulta(familia, id_):
    from lib.catalogo import familias

    escolhida = next(f for f in familias() if f["familia"] == familia)
    return next(p for p in escolhida["pergunta"] if p["id"] == id_)["query"]


def test_disponibilidade_mede_sete_dias_por_componente_com_o_seletor_por_ultimo():
    query = _consulta("cadvisor", "app.disponibilidade_7d")
    assert "avg_over_time(" in query and "[7d:1h]" in query and "30d" not in query
    assert query.count('container_last_seen{name!="",%SELETOR%}') == 2


def test_acerto_soma_acertos_e_erros_do_componente():
    query = _consulta("redis-exporter", "cache.acerto")
    assert query.count("redis_keyspace_hits_total{%SELETOR%}[%JANELA%]") == 2
    assert query.count("redis_keyspace_misses_total{%SELETOR%}[%JANELA%]") == 1


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

    Eu mesmo escorreguei nisto ao acrescentar `cache.taxa_de_acerto` sem arquivo de família
    que a respondesse. Esta trava é o que impede a próxima.
    """
    import tomllib
    from pathlib import Path

    from lib.catalogo import familias

    raiz = Path(__file__).resolve().parents[1] / "references"
    respondidas = {q["id"] for fam in familias() for q in fam.get("pergunta", [])}
    for arquivo in (raiz / "apis").glob("*.toml"):
        dados = tomllib.loads(arquivo.read_text(encoding="utf-8"))
        respondidas |= {q["id"] for q in dados.get("pergunta", [])}

    for arquivo in (raiz / "logs").glob("*.toml"):
        respondidas.add(tomllib.loads(arquivo.read_text(encoding="utf-8"))["pergunta"])

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


def test_hora_sem_scrape_fica_fora_da_media():
    """`vector(0)` existe em toda hora, até na que o Prometheus não raspou nada, e virava 0.

    O ramo que completa a hora vem do cluster inteiro: sem scrape ele some junto, e a hora sai
    da média. Por isso ele não leva `%SELETOR%`: precisa existir quando só o serviço sumiu.
    """
    query = _consulta("cadvisor", "app.disponibilidade_7d")
    assert "vector(0)" not in query
    assert '> bool 0) or 0 * count(container_last_seen{name!=""}))[7d:1h]' in query
