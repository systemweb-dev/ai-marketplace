"""Restrição 3 do spec: produto novo é medido escrevendo arquivos, sem mudar `.py`.

O produto é inventado; o `produtos.toml` e o catálogo são temporários. O runner é o de verdade, com o
subprocesso trocado: é ele que prova que o molde novo foi aceito sem lista no código."""
from unittest import mock

from lib import catalogo_produto, produtos
from lib.adaptadores import produto_ssh
from lib.perguntas import perguntas_do_componente

PRODUTOS = '[[produto]]\nnome = "kvexemplo"\nprocesso = ["kvexemplod"]\nkind = "cache"\n'
CATALOGO = """produto = "kvexemplo"

[cliente]
socket = 'kvexemplo-cli --raw "{sql}"'

[[pergunta]]
id = "cache.memoria_usada"
sql = "STATS memory"
formato = "chave_valor"
separador = "="
campos = { valor = "/bytes_em_uso" }
transformar = { valor = "bytes" }
"""


def test_produto_inventado_e_medido_so_com_arquivos(tmp_path, monkeypatch):
    (tmp_path / "produtos.toml").write_text(PRODUTOS, encoding="utf-8")
    pasta = tmp_path / "produtos-host"
    pasta.mkdir()
    (pasta / "kvexemplo.toml").write_text(CATALOGO, encoding="utf-8")
    monkeypatch.setattr(produtos, "ARQUIVO", tmp_path / "produtos.toml")
    monkeypatch.setattr(catalogo_produto, "PASTA", pasta)
    # papel `app`: `cache.memoria_usada` não é do papel, então só o catálogo a faz ser perguntada
    componente = {"nome": "kv", "papel": "app", "produto": "kvexemplo",
                  "origem": "processo:kvexemplod", "leitura": "socket",
                  "ssh_destino": "root@10.0.0.10", "porta": None}
    saida = mock.Mock(stdout="bytes_em_uso=2048\nchaves=10\n", returncode=0, stderr="")

    with mock.patch("lib.runner.subprocess.run", return_value=saida) as rodou:
        resposta = produto_ssh.perguntar("cache.memoria_usada", componente,
                                         {"timeout": 20, "cache": {}, "alvo": "kv-01"})

    assert resposta == {"pergunta": "cache.memoria_usada", "fonte": "ssh:kvexemplo", "valor": 2048}
    assert rodou.call_args[0][0][-1] == 'kvexemplo-cli --raw "STATS memory"'
    assert "cache.memoria_usada" in [p["id"] for p in perguntas_do_componente(componente)]
