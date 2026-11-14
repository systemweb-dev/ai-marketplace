import subprocess
from unittest import mock

import pytest

from apoio_produto import MARIADB, QDRANT, gravar
from lib import catalogo_host, runner
from lib.coletores.docker_allowlist import NotAllowed

MOLDES = catalogo_host.carregar()["moldes"]
SENHA = 'mariadb --defaults-extra-file=/dev/stdin -N -B -e "{sql}"'
QDRANT_CLIENTE = 'curl -s -f -m 5 "http://127.0.0.1:{porta}{sql}"'


def _ok(stdout="ok\n"):
    return mock.Mock(stdout=stdout, returncode=0, stderr="")


def test_molde_da_camada_comum_monta_o_comando_e_fecha_o_stdin():
    with mock.patch("lib.runner.subprocess.run", return_value=_ok()) as m:
        runner.run_ssh("root@srv-exemplo", None, MOLDES["servico_unidade"], 20,
                       vagas={"unidade": "postgresql@15-main.service"})
    argv, kwargs = m.call_args[0][0], m.call_args[1]
    assert argv[-1] == ("systemctl show postgresql@15-main.service --property=ActiveState,"
                        "ActiveEnterTimestampMonotonic,NRestarts,MemoryCurrent --no-pager")
    assert kwargs["stdin"] is subprocess.DEVNULL and "input" not in kwargs


def test_comando_literal_tambem_fecha_o_stdin():
    with mock.patch("lib.runner.subprocess.run", return_value=_ok()) as m:
        runner.run_ssh("root@srv-exemplo", None, "id -un", 20)
    assert m.call_args[1]["stdin"] is subprocess.DEVNULL


def test_senha_vai_pelo_stdin_e_nunca_pelo_argv(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    entrada = '[client]\nuser="leitor"\npassword="MARCA-senha-123"\n'
    with mock.patch("lib.runner.subprocess.run", return_value=_ok()) as m:
        runner.run_ssh("root@banco-01", None, SENHA, 20, vagas={"sql": "SHOW GLOBAL STATUS"},
                       entrada=entrada)
    argv, kwargs = m.call_args[0][0], m.call_args[1]
    assert argv[-1] == 'mariadb --defaults-extra-file=/dev/stdin -N -B -e "SHOW GLOBAL STATUS"'
    assert not any("MARCA-senha-123" in token for token in argv)
    assert kwargs["input"] == entrada and "stdin" not in kwargs


def test_colecao_valida_entra_na_consulta_do_catalogo(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, qdrant=QDRANT)
    with mock.patch("lib.runner.subprocess.run", return_value=_ok()) as m:
        runner.run_ssh("root@banco-01", None, QDRANT_CLIENTE, 20,
                       vagas={"sql": "/collections/{colecao}", "porta": 6333, "colecao": "docs_v2"})
    assert m.call_args[0][0][-1] == 'curl -s -f -m 5 "http://127.0.0.1:6333/collections/docs_v2"'


RECUSAS = [
    ("molde fora do catálogo", "systemctl show {unidade}", {"unidade": "a.service"}),
    ("unidade com ponto e vírgula", MOLDES["servico_unidade"], {"unidade": "a;reboot"}),
    ("unidade que vira opção", MOLDES["servico_unidade"], {"unidade": "-H evil"}),
    ("container com espaço", MOLDES["servico_container"], {"container": "a b"}),
    ("vaga faltando", MOLDES["servico_unidade"], {}),
    ("vaga sobrando", MOLDES["servico_unidade"], {"unidade": "a.service", "container": "b"}),
    ("pasta que sobe diretório", MOLDES["backup"], {"backup_pasta": "/var/../etc"}),
    ("sql fora do catálogo", SENHA, {"sql": "SELECT 1"}),
    ("sql em molde sem vaga sql", MOLDES["backup"],
     {"backup_pasta": "/var/backups", "sql": "SHOW GLOBAL STATUS"}),
    ("coleção com ponto e vírgula", QDRANT_CLIENTE,
     {"sql": "/collections/{colecao}", "porta": 6333, "colecao": "a;b"}),
    ("coleção com espaço", QDRANT_CLIENTE,
     {"sql": "/collections/{colecao}", "porta": 6333, "colecao": "a b"}),
    ("porta fora da faixa", QDRANT_CLIENTE, {"sql": "/collections", "porta": 0}),
]


@pytest.mark.parametrize("caso,molde,vagas", RECUSAS, ids=[r[0] for r in RECUSAS])
def test_runner_recusa_antes_do_subprocesso(tmp_path, monkeypatch, caso, molde, vagas):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB, qdrant=QDRANT)
    with mock.patch("lib.runner.subprocess.run") as m:
        with pytest.raises(NotAllowed):
            runner.run_ssh("root@banco-01", None, molde, 20, vagas=vagas)
    assert m.call_count == 0


def test_a_recusa_nao_repete_o_valor_recusado():
    with pytest.raises(NotAllowed) as erro:
        runner.run_ssh("root@banco-01", None, MOLDES["servico_unidade"], 20,
                       vagas={"unidade": "a;reboot"})
    assert "reboot" not in str(erro.value) and "{unidade}" in str(erro.value)


def test_codigo_de_saida_vai_junto_do_motivo():
    erros = []
    falha = mock.Mock(stdout="", returncode=127, stderr="bash: mariadb: command not found")
    with mock.patch("lib.runner.subprocess.run", return_value=falha):
        assert runner.run_ssh("root@banco-01", None, "id -un", 20, errors=erros) is None
    assert erros == [{"cmd": "ssh root@banco-01", "reason": "bash: mariadb: command not found",
                      "codigo": 127}]