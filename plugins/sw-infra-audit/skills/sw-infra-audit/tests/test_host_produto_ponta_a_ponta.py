# tests/test_host_produto_ponta_a_ponta.py
"""Restrição 1 do spec, pelo caminho real: a senha marcada vai pelo stdin do ssh e não aparece em
nenhum argv nem no report.json. Só o subprocesso é de mentira."""
import json
from unittest import mock

import collect

MARCA = "MARCA7f3e"
SENHA = f'{MARCA}"#\\fim'          # aspas, `#` e barra: o escape é exercitado junto
ALVOS = """[[alvo]]
nome = "banco-01"
tipo = "host"
ssh_destino = "root@10.0.0.10"

[[alvo.componente]]
nome = "mariadb"
papel = "banco"
produto = "mariadb"
portas = [3306]
origem = "unidade:mariadb.service"
leitura = "senha"
usuario = "leitor"
senha_env = "SENHA_DO_BANCO_TESTE"
backup_pasta = "/var/backups/mysql"
"""
# (trecho do comando remoto, stdout, código, stderr) — o primeiro trecho contido no comando vence
RESPOSTAS = [
    ("id -un", "root\n", 0, ""),
    ("uname -sr", "Linux 6.1.0-18-amd64\n", 0, ""),
    ("cat /etc/os-release", 'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\n', 0, ""),
    ("df -P -k", "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
                 "/dev/vda1 50000000 10000000 40000000 20% /\n", 0, ""),
    ("cat /proc/meminfo", "MemTotal: 4000000 kB\nMemAvailable: 2000000 kB\n", 0, ""),
    ("cat /proc/loadavg", "0.40 0.80 0.60 1/100 1\n", 0, ""),
    ("nproc", "2\n", 0, ""),
    ("cat /proc/uptime", "259200.00 10.00\n", 0, ""),
    ("systemctl show mariadb.service", "ActiveState=active\nActiveEnterTimestampMonotonic="
                                       "86400000000\nNRestarts=0\nMemoryCurrent=524288000\n", 0, ""),
    ("systemctl list-units", "mariadb.service loaded active running MariaDB\n", 0, ""),
    ("ss -ltnpH", 'LISTEN 0 80 127.0.0.1:3306 0.0.0.0:* users:(("mariadbd",pid=812,fd=22))\n', 0, ""),
    ("docker ps", "", 0, ""),
    ("SHOW GLOBAL STATUS", "Slow_queries\t7\nThreads_connected\t12\n", 0, ""),
    ("SHOW GLOBAL VARIABLES", "max_connections\t14\n", 0, ""),
    ("SHOW BINARY LOGS", "", 1, "ERROR 1381 (HY000) at line 1: You are not using binary logging"),
    ("GROUP BY table_schema", "app\t700000000\n", 0, ""),
    ("information_schema.tables", "700000000\n", 0, ""),
    ("ls -l --time-style=full-iso /var/backups/mysql",
     "total 4\n-rw-r--r-- 1 root root 10 2026-11-08 03:00:00.000000000 +0000 "
     "dump-2026-11-08.sql.gz\n", 0, ""),
]


def test_senha_so_pelo_stdin_e_o_resto_do_host_medido(tmp_path, monkeypatch, capsys):
    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(ALVOS, encoding="utf-8")
    (tmp_path / "alvos.toml").chmod(0o600)
    (tmp_path / "config.toml").write_text('alvos = ["banco-01"]\n', encoding="utf-8")
    monkeypatch.setenv("SENHA_DO_BANCO_TESTE", SENHA)
    chamadas = []

    def falso(cmd, **kwargs):
        chamadas.append((list(cmd), kwargs))
        for trecho, stdout, codigo, stderr in RESPOSTAS:
            if trecho in cmd[-1]:
                return mock.Mock(stdout=stdout, returncode=codigo, stderr=stderr)
        return mock.Mock(stdout="", returncode=1, stderr="sem resposta falsa para este comando")

    with mock.patch("lib.runner.subprocess.run", side_effect=falso):
        codigo = collect.main(["--padrao", str(tmp_path / "default.toml"),
                               "--infra", str(tmp_path / "alvos.toml"),
                               "--projeto", str(tmp_path / "config.toml"),
                               "--out", str(tmp_path / "saida"), "--at", "2026-11-13T10:00:00Z",
                               "--confirmar", "banco-01"])
    texto = (tmp_path / "saida" / "report.json").read_text(encoding="utf-8")

    assert codigo == 0
    assert not any(MARCA in token for argv, _ in chamadas for token in argv)
    assert any(MARCA in (kwargs.get("input") or "") for _, kwargs in chamadas)
    assert MARCA not in texto
    saida = capsys.readouterr()
    assert MARCA not in saida.out and MARCA not in saida.err
    # o patch troca TODO `subprocess.run` do módulo, inclusive o `git` de exigir_pasta_protegida:
    # a regra vale só para as chamadas de ssh
    assert all(("input" in kwargs) != ("stdin" in kwargs)
               for argv, kwargs in chamadas if argv[0] == "ssh")

    alvo = json.loads(texto)["alvos"][0]
    mariadb = next(c for c in alvo["componentes"] if c["nome"] == "mariadb")
    respostas = {r["pergunta"]: r for r in mariadb["respostas"]}
    assert respostas["banco.conexoes"]["valor"] == 12
    assert respostas["banco.conexoes"]["fonte"] == "ssh:mariadb"
    assert respostas["servico.ativo"]["valor"] == "ativo"
    assert respostas["banco.backup_idade"]["valor"] == 5
    assert respostas["banco.binlog"]["nao_publica"] is True
    assert {"backup_atrasado", "conexoes_no_limite"} <= {a["regra"] for a in alvo["achados"]}
