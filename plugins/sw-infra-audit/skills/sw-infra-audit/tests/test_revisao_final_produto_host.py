# tests/test_revisao_final_produto_host.py
"""Achados das revisões finais da coleta por produto em servidores host."""
import subprocess

import pytest

import configurar
from apoio_host import runner_falso
from apoio_produto import MARIADB, gravar
from lib import alvos, runner
from lib.adaptadores import produto_ssh, ssh
from test_leitura_servico import SHOW

# o cliente encadeia comando: o carregador recusa o arquivo inteiro
QUEBRADO = 'produto = "qdrant"\n\n[cliente]\nsocket = \'curl -s "{sql}"; reboot\'\n'


def _ctx():
    return {"timeout": 20, "cache": {}, "alvo": "banco-01", "at": "2026-11-13T10:00:00Z"}


def _subprocess_falso(saidas):
    """O ssh de verdade sai do caminho só no `subprocess.run`: o molde passa por `vagas.preencher`."""
    def run(cmd, **_):
        remoto = cmd[-1]
        saida = next((s for trecho, s in saidas.items() if trecho in remoto), None)
        if saida is None:
            return subprocess.CompletedProcess(cmd, 1, "", "falhou")
        return subprocess.CompletedProcess(cmd, 0, saida, "")
    return run


# 1 — catálogo inválido de UM produto não derruba os outros

def test_catalogo_invalido_de_outro_produto_nao_derruba_servico_do_ssh(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB, qdrant=QUEBRADO)
    monkeypatch.setattr(runner.subprocess, "run",
                        _subprocess_falso({"systemctl": SHOW, "proc/uptime": "259200.00 1.00\n"}))
    componente = {"nome": "mariadb", "papel": "banco", "ssh_destino": "root@banco-01",
                  "porta": None, "origem": "unidade:mariadb.service"}
    assert ssh.perguntar("servico.ativo", componente, _ctx())["valor"] == "ativo"


def test_catalogo_invalido_de_outro_produto_nao_derruba_o_produto_valido(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB, qdrant=QUEBRADO)
    monkeypatch.setattr(runner.subprocess, "run",
                        _subprocess_falso({"SHOW GLOBAL STATUS": "Threads_connected\t12\n"}))
    componente = {"nome": "mariadb", "papel": "banco", "produto": "mariadb", "leitura": "socket",
                  "origem": "unidade:mariadb.service", "ssh_destino": "root@banco-01",
                  "porta": None}
    assert produto_ssh.perguntar("banco.conexoes", componente, _ctx())["valor"] == 12


def test_pergunta_do_produto_de_catalogo_invalido_diz_qual_e_o_motivo(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB, qdrant=QUEBRADO)
    componente = {"nome": "qdrant", "papel": "busca", "produto": "qdrant", "leitura": "socket",
                  "origem": "unidade:qdrant.service", "ssh_destino": "root@banco-01",
                  "porta": None}
    resposta = produto_ssh.perguntar("busca.colecoes", componente, _ctx())
    assert resposta["sem_dados"]
    assert resposta["motivo"].startswith("catálogo de qdrant inválido: qdrant.toml:")


# 2 — taxa sem leitura nenhuma é indefinida por desenho, não formato inesperado

def test_redis_sem_leitura_nenhuma_e_taxa_indefinida_e_nao_publica(monkeypatch):
    componente = {"nome": "redis", "papel": "cache", "produto": "redis", "leitura": "socket",
                  "origem": "unidade:redis-server.service", "ssh_destino": "root@banco-01",
                  "porta": None}
    monkeypatch.setattr(produto_ssh.runner, "run_ssh",
                        runner_falso({"INFO": "keyspace_hits:0\r\nkeyspace_misses:0\r\n"}))
    resposta = produto_ssh.perguntar("cache.acerto", componente, _ctx())
    assert resposta["sem_dados"] and resposta["nao_publica"] is True
    assert resposta["motivo"] == "sem leituras ainda: taxa indefinida"


def test_redis_sem_os_campos_continua_formato_inesperado(monkeypatch):
    componente = {"nome": "redis", "papel": "cache", "produto": "redis", "leitura": "socket",
                  "origem": "unidade:redis-server.service", "ssh_destino": "root@banco-01",
                  "porta": None}
    monkeypatch.setattr(produto_ssh.runner, "run_ssh", runner_falso({"INFO": "used_memory:1\r\n"}))
    resposta = produto_ssh.perguntar("cache.acerto", componente, _ctx())
    assert resposta["motivo"] == produto_ssh.FORA_DO_FORMATO and "nao_publica" not in resposta


# 4 — campos de componente de host só valem em alvo host

@pytest.mark.parametrize("campo", ['origem = "unidade:mariadb.service"', 'leitura = "socket"',
                                   'backup_pasta = "/var/backups"'])
def test_campo_de_host_em_componente_de_alvo_docker_e_recusado(tmp_path, campo):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text('[[alvo]]\nnome = "prod"\ntipo = "docker"\ncontext = "prod"\n'
                       f'[[alvo.componente]]\nnome = "mariadb"\npapel = "banco"\n{campo}\n',
                       encoding="utf-8")
    caminho.chmod(0o600)
    with pytest.raises(alvos.AlvoInvalido, match="só vale em alvo host"):
        alvos.ler(caminho)


# 7 — leitura só para banco, cache ou busca

def test_configurar_leitura_recusa_componente_que_nao_e_banco_cache_nem_busca(tmp_path, capsys):
    caminho = tmp_path / "alvos.toml"
    caminho.write_text('[[alvo]]\nnome = "web-01"\ntipo = "host"\nssh_destino = "root@10.0.0.10"\n'
                       '[[alvo.componente]]\nnome = "nginx"\npapel = "entrada"\n'
                       'origem = "unidade:nginx.service"\n', encoding="utf-8")
    caminho.chmod(0o600)
    antes = caminho.read_text(encoding="utf-8")
    codigo = configurar.main(["leitura", "--alvo", "web-01", "--componente", "nginx",
                              "--modo", "socket", "--infra", str(caminho)])
    assert codigo != 0
    assert "leitura só vale para componente de papel banco, cache ou busca" in capsys.readouterr().err
    assert caminho.read_text(encoding="utf-8") == antes
