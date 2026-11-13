import difflib

import pytest

import configurar
from apoio_host import runner_falso
from lib import gravacao_alvos as g
from test_configurar_descobrir import SAIDAS

TEXTO = ('# meus alvos\n[[alvo]]\nnome = "banco-01"\ntipo = "host"\nssh_destino = "root@banco-01"\n'
         '\n# o cluster\n[[alvo]]\nnome = "prod"\ntipo = "docker"\ncontext = "prod"\n')
COMP = {"nome": "mariadb", "papel": "banco", "produto": "mariadb", "portas": [3306],
        "origem": "unidade:mariadb.service"}


def test_insere_depois_do_bloco_certo_e_so_acrescenta_linhas():
    novo = g.inserir(TEXTO, "banco-01", [COMP], "2026-11-13")
    diff = [l for l in difflib.ndiff(TEXTO.splitlines(), novo.splitlines()) if l[:1] in "+-"]
    assert all(l.startswith("+") for l in diff)
    assert novo.index("[[alvo.componente]]") < novo.index("# o cluster")


def test_alvo_inexistente_e_recusado():
    with pytest.raises(g.GravacaoInvalida):
        g.inserir(TEXTO, "nao-existe", [COMP], "2026-11-13")


def test_componente_nao_gravavel_e_recusado_antes_de_escrever():
    with pytest.raises(g.GravacaoInvalida):
        g.inserir(TEXTO, "banco-01", [dict(COMP, origem='processo:x"]\n[[alvo]]')], "2026-11-13")


def _arquivo(tmp_path):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text(TEXTO, encoding="utf-8")
    caminho.chmod(0o600)
    return caminho


def test_gravar_pelo_cli_acrescenta_e_deixa_o_bak(tmp_path, monkeypatch):
    caminho = _arquivo(tmp_path)
    monkeypatch.setattr("lib.runner.run_ssh", runner_falso(SAIDAS))
    codigo = configurar.main(["descobrir", "--alvo", "banco-01", "--infra", str(caminho),
                              "--gravar", "mariadb"])
    texto = caminho.read_text(encoding="utf-8")
    assert codigo == 0 and 'origem = "unidade:mariadb.service"' in texto
    assert (tmp_path / "alvos.toml.bak").read_text(encoding="utf-8") == TEXTO
    assert configurar.main(["descobrir", "--alvo", "banco-01", "--infra", str(caminho),
                            "--gravar", "mariadb"]) == 0
    assert caminho.read_text(encoding="utf-8").count("[[alvo.componente]]") == 1


def test_releitura_que_falha_restaura_o_original(tmp_path, monkeypatch):
    caminho = _arquivo(tmp_path)
    monkeypatch.setattr("lib.runner.run_ssh", runner_falso(SAIDAS))
    monkeypatch.setattr(g, "inserir", lambda texto, *a: texto + "[[alvo]]\nnome = \"invasor\"\n")
    assert configurar.main(["descobrir", "--alvo", "banco-01", "--infra", str(caminho),
                            "--gravar", "mariadb"]) == 2
    assert caminho.read_text(encoding="utf-8") == TEXTO


def test_nome_inexistente_em_gravar_e_recusado(tmp_path, monkeypatch, capsys):
    caminho = _arquivo(tmp_path)
    monkeypatch.setattr("lib.runner.run_ssh", runner_falso(SAIDAS))
    assert configurar.main(["descobrir", "--alvo", "banco-01", "--infra", str(caminho),
                            "--gravar", "fantasma"]) == 2
    assert caminho.read_text(encoding="utf-8") == TEXTO
