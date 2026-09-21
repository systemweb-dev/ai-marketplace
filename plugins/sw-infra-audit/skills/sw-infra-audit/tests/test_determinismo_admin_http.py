# tests/test_determinismo_admin_http.py
"""Mesma entrada, mesmo byte — inclusive quando a API muda a ordem.

A quinta restrição verificável do spec. A API de administração não promete ordem na listagem
de filas, e empates são a regra, não a exceção: centenas de filas com o mesmo número de
mensagens, o mesmo nome em vhosts diferentes. Se a ordem da resposta vazasse para o relatório,
duas auditorias do mesmo broker, parado, dariam relatórios diferentes — e o diff entre rodadas
acusaria mudança onde nada mudou.
"""
import json
import random

import collect
from lib import adaptadores, http_get

FILAS = ([{"name": f"orfa-{n:03d}", "vhost": v, "messages_ready": 5, "consumers": 0}
          for n in range(40) for v in ("/", "staging")]
         + [{"name": f"cheia-{n}", "vhost": "/", "messages_ready": 900, "consumers": 2,
             "message_stats": {"publish_details": {"rate": 3.0},
                               "deliver_get_details": {"rate": 3.0}}} for n in range(15)])


def _rodar(tmp_path, monkeypatch, filas, pasta):
    def rede(url, permitidos, credencial, alvo=None, timeout=None):
        if url.split("?")[0].endswith("/api/overview"):
            return 200, json.dumps({"product_name": "X", "rabbitmq_version": "4.0"})
        return 200, json.dumps(filas)

    monkeypatch.setattr(http_get, "get_autenticado", rede)

    def coletor(alvo, contexto):
        return {"saude": "🟢", "componentes": [
            {"nome": "broker", "papel": "fila", "admin_url": "http://exemplo.test:15672"}]}

    for nome, texto in (("default.toml", '[relatorio]\npasta = "x"\n'),
                        ("alvos.toml", '[[alvo]]\nnome = "p"\ntipo = "docker"\ncontext = "p"\n'),
                        ("config.toml", 'alvos = ["p"]\n')):
        (tmp_path / nome).write_text(texto, encoding="utf-8")
    collect.main(["--padrao", str(tmp_path / "default.toml"),
                  "--infra", str(tmp_path / "alvos.toml"),
                  "--projeto", str(tmp_path / "config.toml"), "--out", str(tmp_path / pasta),
                  "--at", "2026-09-21T10:00:00Z", "--confirmar", "p"],
                 coletores={"docker": coletor}, adaptadores=adaptadores.todos())
    return (tmp_path / pasta / "report.json").read_bytes()


def test_a_ordem_da_api_nao_vaza_para_o_relatorio(tmp_path, monkeypatch):
    embaralhadas = list(FILAS)
    random.Random(7).shuffle(embaralhadas)

    primeira = _rodar(tmp_path, monkeypatch, FILAS, "a")
    segunda = _rodar(tmp_path, monkeypatch, embaralhadas, "b")

    assert primeira == segunda


def test_o_relatorio_exercita_os_empates(tmp_path, monkeypatch):
    """Sem empate, o teste acima passaria por acaso: garante que eles existem na entrada."""
    relatorio = json.loads(_rodar(tmp_path, monkeypatch, FILAS, "c"))
    achados = relatorio["alvos"][0]["achados"]

    assert len(achados) == 80
    assert {a["objeto"] for a in achados} >= {"orfa-000@/", "orfa-000@staging"}


def test_o_report_json_nao_tem_nan(tmp_path, monkeypatch):
    """NaN escrito no report.json produz JSON inválido para qualquer leitor fora do Python."""
    filas = [dict(f, messages_ready=float("nan")) for f in FILAS[:3]] + FILAS[3:]

    json.loads(_rodar(tmp_path, monkeypatch, filas, "d"),
               parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
