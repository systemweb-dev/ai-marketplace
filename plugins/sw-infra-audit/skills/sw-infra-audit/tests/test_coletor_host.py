# tests/test_coletor_host.py
import json

import collect
from apoio_host import SAIDAS_PADRAO, runner_falso
from lib import adaptadores
from lib.coletores import host

ALVO = {"nome": "banco-01", "tipo": "host", "ssh_destino": "root@banco-01", "componente": []}


def _ctx():
    return {"timeout": 20, "http_timeout": 8, "orcamento": 120, "orcamento_urls": 120,
            "janela": "24h", "at": "2026-11-13T10:00:00Z"}


def _coletar(monkeypatch, saidas, conexao=True):
    monkeypatch.setattr("lib.runner.run_ssh", runner_falso(saidas, conexao=conexao))
    return collect.coletar_alvo(dict(ALVO), host.coletar, _ctx(), adaptadores.todos())


def test_host_traz_usuario_acesso_e_maquina_com_disco_e_achado(monkeypatch):
    registro = _coletar(monkeypatch, SAIDAS_PADRAO)
    assert registro["onde"] == "ssh: root@banco-01"
    assert registro["fatos"]["usuario"] == "root"
    assert "identidade SSH de quem executou a auditoria (root)" in registro["fatos"]["acesso"]
    maquina = registro["componentes"][0]
    disco = next(r for r in maquina["respostas"] if r["pergunta"] == "maquina.disco")
    assert disco["valor"] == 94 and disco["fonte"] == "ssh"
    assert [a["regra"] for a in registro["achados"]] == ["disco_quase_cheio"]


def test_vpn_desligada_e_sem_dados_com_motivo_e_zero_achados(monkeypatch):
    registro = _coletar(monkeypatch, SAIDAS_PADRAO, conexao=False)
    assert registro["achados"] == []
    assert any("VPN" in str(n) for n in registro["nao_coletado"])


def test_mesma_entrada_mesmo_byte(monkeypatch):
    primeiro = _coletar(monkeypatch, SAIDAS_PADRAO)
    segundo = _coletar(monkeypatch, SAIDAS_PADRAO)
    assert json.dumps(primeiro, sort_keys=True) == json.dumps(segundo, sort_keys=True)


def test_acesso_restrito_troca_o_texto(monkeypatch):
    monkeypatch.setattr("lib.runner.run_ssh", runner_falso(SAIDAS_PADRAO))
    registro = collect.coletar_alvo(dict(ALVO, acesso_restrito=True), host.coletar, _ctx(),
                                    adaptadores.todos())
    assert registro["fatos"]["acesso"].startswith("Acesso restrito no servidor")
