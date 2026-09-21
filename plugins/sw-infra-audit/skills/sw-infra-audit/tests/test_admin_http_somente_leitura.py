# tests/test_admin_http_somente_leitura.py
"""As travas que fazem "somente leitura" e "a senha não vaza" serem verificáveis.

Rede e subprocesso fora do dono já são barrados para qualquer adaptador em
`test_restricoes.py`. Aqui fica o que é próprio da primeira porta AUTENTICADA da skill: a API
de administração tem rotas que purgam fila, publicam mensagem e removem exchange, e uma linha
errada — um `method=` a mais, um caminho de escrita no catálogo — transformaria auditoria em
operação.
"""
import ast
import json
import re
from pathlib import Path

import collect
from lib import http_get
from lib.catalogo_api import PASTA, familias

SCRIPTS = Path(collect.__file__).resolve().parent
SENHA = "s3gr3do-que-nao-pode-aparecer"


def test_nenhum_adaptador_le_variavel_de_ambiente():
    """A senha sai do ambiente num lugar só (`lib/credencial.py`). Adaptador que lê
    `os.environ` por conta própria escapa da amarração (alvo, host, porta)."""
    culpados = [arquivo.name for arquivo in (SCRIPTS / "lib" / "adaptadores").glob("*.py")
                if re.search(r"environ|getenv", arquivo.read_text(encoding="utf-8"))]

    assert culpados == []


def test_get_autenticado_so_faz_get():
    """O único lugar da skill que manda credencial fixa o método. Verificado no código, e não
    só pelo comportamento: um parâmetro `method=` acrescentado amanhã teria default GET e os
    testes de comportamento continuariam verdes."""
    arvore = ast.parse((SCRIPTS / "lib" / "http_get.py").read_text(encoding="utf-8"))
    funcao = next(no for no in ast.walk(arvore)
                  if isinstance(no, ast.FunctionDef) and no.name == "get_autenticado")

    metodos = [kw.value.value for no in ast.walk(funcao) if isinstance(no, ast.Call)
               for kw in no.keywords if kw.arg == "method"]
    parametros = [a.arg for a in funcao.args.args]

    assert metodos == ["GET"]
    assert "method" not in parametros


def test_get_autenticado_passa_pela_allowlist():
    import pytest

    with pytest.raises(http_get.NotConfirmed):
        http_get.get_autenticado("http://fora.test:15672/api/overview", [], None)


def test_nenhum_catalogo_alcanca_rota_de_escrita():
    """Vale para TODA família, não só a que existe hoje. Escrita nesta classe de API é ROTA
    (`/contents`, `/purge`, `/publish`, `/actions`); o único parâmetro aceito é `columns`, que
    só escolhe o que ler."""
    for familia in familias():
        caminhos = [familia["identificacao"]["caminho"]]
        caminhos += [p["caminho"] for p in familia.get("pergunta", [])]
        for caminho in caminhos:
            rota, _, consulta = caminho.partition("?")
            for palavra in ("delete", "purge", "publish", "create", "reset", "close", "move",
                            "contents", "actions", "restart", "rebalance"):
                assert palavra not in rota.lower(), f"{familia['familia']}: {rota}"
            for parametro in filter(None, consulta.split("&")):
                assert parametro.split("=")[0] == "columns", f"{familia['familia']}: {parametro}"


def test_a_pasta_de_catalogo_e_a_que_o_adaptador_le():
    """Travar a pasta errada seria travar nada."""
    assert (PASTA / "amqp-mgmt.toml").exists()


def test_a_senha_nao_chega_ao_report_nem_ao_html(tmp_path, monkeypatch):
    """De ponta a ponta, pelo caminho de produção: alvos.toml com `senha_env`, coletor docker
    copiando o componente, `admin_http` autenticando, relatório gerado. A senha precisa passar
    pelo header e não sobreviver em nenhum arquivo."""
    import build_report

    monkeypatch.setenv("SENHA_BROKER", SENHA)
    vistas = []

    def rede(url, permitidos, credencial, alvo=None, timeout=None):
        vistas.append(credencial.para(url, alvo) if credencial else None)
        if url.split("?")[0].endswith("/api/overview"):
            return 200, json.dumps({"product_name": "X", "rabbitmq_version": "4.0"})
        return 200, json.dumps([{"name": "emails", "vhost": "/", "messages_ready": 7,
                                 "consumers": 0}])

    monkeypatch.setattr(http_get, "get_autenticado", rede)

    def coletor(alvo, contexto):
        return {"saude": "🟢", "componentes": [
            {"nome": "broker", "papel": "fila", "admin_url": "http://exemplo.test:15672",
             "senha_env": "SENHA_BROKER", "usuario": "leitor"}]}

    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "x"\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "prod"\ntipo = "docker"\ncontext = "prod"\n', encoding="utf-8")
    (tmp_path / "config.toml").write_text('alvos = ["prod"]\n', encoding="utf-8")
    from lib import adaptadores

    collect.main(["--padrao", str(tmp_path / "default.toml"),
                  "--infra", str(tmp_path / "alvos.toml"),
                  "--projeto", str(tmp_path / "config.toml"), "--out", str(tmp_path / "saida"),
                  "--at", "2026-09-21T10:00:00Z", "--confirmar", "prod"],
                 coletores={"docker": coletor}, adaptadores=adaptadores.todos())
    relatorio = json.loads((tmp_path / "saida" / "report.json").read_text(encoding="utf-8"))
    build_report.build(relatorio, tmp_path / "saida", formato="html")

    assert ("leitor", SENHA) in vistas, "a credencial nem chegou à requisição — teste inútil"
    for arquivo in (tmp_path / "saida").iterdir():
        assert SENHA not in arquivo.read_text(encoding="utf-8", errors="replace"), arquivo.name
    assert relatorio["alvos"][0]["achados"], "sem achado, o relatório não exercitou o caminho"
