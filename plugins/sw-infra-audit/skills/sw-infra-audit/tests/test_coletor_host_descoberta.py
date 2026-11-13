# tests/test_coletor_host_descoberta.py
import collect
from apoio_host import SAIDAS_PADRAO, runner_falso
from lib import adaptadores
from lib.coletores import host
from test_descoberta import CONTAINERS, PORTAS, SERVICOS

SAIDAS = dict(SAIDAS_PADRAO, servicos=SERVICOS, portas=PORTAS, containers=CONTAINERS)
MARIADB = {"nome": "mariadb", "papel": "banco", "produto": "mariadb", "portas": [3306],
           "origem": "unidade:mariadb.service"}
SUMIDO = {"nome": "pg", "papel": "banco", "produto": "postgres", "portas": [5432],
          "origem": "unidade:postgresql.service"}


def _coletar(monkeypatch, saidas, componentes):
    monkeypatch.setattr("lib.runner.run_ssh", runner_falso(saidas))
    alvo = {"nome": "banco-01", "tipo": "host", "ssh_destino": "root@banco-01",
            "componente": componentes}
    ctx = {"timeout": 20, "http_timeout": 8, "orcamento": 120, "orcamento_urls": 120,
           "janela": "24h", "at": "2026-11-13T10:00:00Z"}
    return collect.coletar_alvo(alvo, host.coletar, ctx, adaptadores.todos())


def _regras(registro):
    return sorted((a["regra"], a["componente"]) for a in registro["achados"])


def test_banco_em_todas_as_interfaces_e_servico_sumido_viram_achado(monkeypatch):
    registro = _coletar(monkeypatch, SAIDAS, [MARIADB, SUMIDO])
    assert ("SEC_BIND_ALL_INTERFACES", "mariadb") in _regras(registro)
    assert ("servico_declarado_ausente", "pg") in _regras(registro)


def test_fonte_que_falhou_nao_acusa_ausencia(monkeypatch):
    saidas = {k: v for k, v in SAIDAS.items() if k != "servicos"}
    registro = _coletar(monkeypatch, saidas, [SUMIDO])
    assert ("servico_declarado_ausente", "pg") not in _regras(registro)
    assert any("não medido" in str(n) and "pg" in str(n) for n in registro["nao_coletado"])


def test_encontrado_e_nao_declarado_vira_nota_e_nao_achado(monkeypatch):
    registro = _coletar(monkeypatch, SAIDAS, [MARIADB])
    assert any("descoberto e não declarado" in str(n) and "qdrant" in str(n)
               for n in registro["nao_coletado"])
    assert all(a["componente"] != "qdrant" for a in registro["achados"])
