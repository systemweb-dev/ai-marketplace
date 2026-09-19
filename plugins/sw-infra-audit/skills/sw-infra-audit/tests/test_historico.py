# tests/test_historico.py
import json

from lib.historico import comparar, pasta_anterior


def gravar(pasta, relatorio):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "report.json").write_text(json.dumps(relatorio), encoding="utf-8")
    return pasta


def v2(alvos):
    return {"schema_version": 2, "alvos": alvos}


def test_acha_a_execucao_anterior_pelo_nome_da_pasta(tmp_path):
    raiz = tmp_path / "docs" / "infra"
    gravar(raiz / "2026-09-18_0900", v2([]))
    gravar(raiz / "2026-09-18_1500", v2([]))
    atual = gravar(raiz / "2026-09-19_1000", v2([]))

    assert pasta_anterior(atual).name == "2026-09-18_1500"


def test_ignora_relatorio_de_schema_antigo(tmp_path):
    raiz = tmp_path / "docs" / "infra"
    gravar(raiz / "2026-09-18_0900", {"schema_version": 1, "cluster": {}})
    atual = gravar(raiz / "2026-09-19_1000", v2([]))

    assert pasta_anterior(atual) is None


def test_sem_execucao_anterior_devolve_nada(tmp_path):
    atual = gravar(tmp_path / "docs" / "infra" / "2026-09-19_1000", v2([]))

    assert pasta_anterior(atual) is None


def test_diff_usa_alvo_regra_e_objeto_como_chave(tmp_path):
    anterior = v2([{"nome": "a", "achados": [{"regra": "spof", "objeto": "web", "alvo": "a"}]},
                   {"nome": "b", "achados": [{"regra": "spof", "objeto": "web", "alvo": "b"}]}])
    atual = v2([{"nome": "a", "achados": []},
                {"nome": "b", "achados": [{"regra": "spof", "objeto": "web", "alvo": "b"},
                                          {"regra": "sem_tls", "objeto": "api", "alvo": "b"}]}])

    diff = comparar(anterior, atual, nome_anterior="2026-09-18_1500")

    assert diff["vs"] == "2026-09-18_1500"
    assert diff["resolvidos"] == ["a · spof · web"]
    assert diff["novos"] == ["b · sem_tls · api"]


def test_serviço_homonimo_em_alvos_diferentes_nao_colide(tmp_path):
    """Sem o alvo na chave, 'spof · web' de dois clusters viraria o mesmo achado."""
    anterior = v2([{"nome": "a", "achados": [{"regra": "spof", "objeto": "web", "alvo": "a"}]}])
    atual = v2([{"nome": "b", "achados": [{"regra": "spof", "objeto": "web", "alvo": "b"}]}])

    diff = comparar(anterior, atual, nome_anterior="x")

    assert diff["resolvidos"] == ["a · spof · web"]
    assert diff["novos"] == ["b · spof · web"]
