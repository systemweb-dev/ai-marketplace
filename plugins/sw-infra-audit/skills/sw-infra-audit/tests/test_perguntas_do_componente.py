# tests/test_perguntas_do_componente.py
import pytest

import collect
from apoio_host import SAIDAS_PADRAO, runner_falso
from apoio_produto import gravar
from lib import adaptadores
from lib.cobertura import medir
from lib.coletores import host
from lib.orcamento import Prazo
from lib.perguntas import COMUNS, perguntas_do_componente
from test_leitura_servico import SHOW

# O que `do_papel` devolvia na v0.20.0: é EXATAMENTE isto que um componente de alvo docker recebe.
ANTES = {
    "entrada": ["entrada.volume_na_janela", "entrada.distribuicao_de_status", "entrada.latencia",
                "entrada.por_servico", "entrada.urls_mais_acessadas"],
    "fila": ["fila.filas", "fila.consumidores_por_fila", "fila.taxa_entrada_saida"],
    "app": ["app.cpu", "app.memoria", "app.disponibilidade_7d"],
    "banco": ["banco.conexoes", "banco.tamanho"],
    "cache": ["cache.memoria_usada", "cache.evicções", "cache.acerto"],
    "busca": [], "storage": [], "observabilidade": [],
    "maquina": ["maquina.cpu", "maquina.memoria", "maquina.disco", "maquina.disco_dias",
                "maquina.carga", "maquina.desde_o_boot"],
}
CATALOGO = """produto = "mariadb"

[cliente]
socket = 'mariadb -N -B -e "{sql}"'

[[pergunta]]
id = "banco.tamanho"
sql = "SELECT 1"
formato = "tsv"
colunas = ["valor"]
campos = { valor = "/linhas/0/valor" }

[[pergunta]]
id = "cache.acerto"
sql = "SELECT 2"
formato = "tsv"
colunas = ["valor"]
campos = { valor = "/linhas/0/valor" }
"""


@pytest.mark.parametrize("papel", sorted(ANTES))
def test_componente_de_alvo_docker_recebe_as_mesmas_perguntas_de_antes(papel, tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=CATALOGO)
    componente = {"nome": "x", "papel": papel, "produto": "mariadb",
                  "backup_pasta": "/var/backups"}
    assert [p["id"] for p in perguntas_do_componente(componente)] == ANTES[papel]


class Anota:
    ID = "anota"

    def __init__(self):
        self.perguntas = []

    def perguntar(self, pergunta, componente, contexto):
        self.perguntas.append((componente["nome"], pergunta))
        return {"pergunta": pergunta, "fonte": "anota", "valor": 1}


def test_coleta_de_alvo_docker_pergunta_o_mesmo_que_antes(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=CATALOGO)
    anota = Anota()

    def coletor(alvo, contexto):
        return {"saude": "🟢", "componentes": [{"nome": "db", "papel": "banco",
                                                 "papel_origem": "declarado", "produto": "mariadb"}]}

    collect.coletar_alvo({"nome": "prod", "tipo": "docker", "context": "prod"}, coletor,
                         {"timeout": 5, "orcamento": 30, "orcamento_urls": 30,
                          "at": "2026-11-13T10:00:00Z"}, [anota])
    assert [p for nome, p in anota.perguntas if nome == "db"] == ANTES["banco"]


def test_componente_de_host_ganha_as_comuns_e_o_backup():
    componente = {"nome": "mariadb", "papel": "banco", "origem": "unidade:mariadb.service",
                  "backup_pasta": "/var/backups/mysql"}
    assert [p["id"] for p in perguntas_do_componente(componente)] == \
        ["banco.conexoes", "banco.tamanho", *COMUNS, "banco.backup_idade"]


def test_catalogo_do_produto_entra_uma_vez_so(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=CATALOGO)
    componente = {"nome": "mariadb", "papel": "banco", "produto": "mariadb",
                  "origem": "unidade:mariadb.service"}
    assert [p["id"] for p in perguntas_do_componente(componente)] == \
        ["banco.conexoes", "banco.tamanho", *COMUNS, "cache.acerto"]


def test_catalogo_invalido_nao_derruba_e_fica_de_fora(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb='produto = "mariadb"\n')
    componente = {"nome": "mariadb", "papel": "banco", "produto": "mariadb",
                  "origem": "unidade:mariadb.service"}
    assert [p["id"] for p in perguntas_do_componente(componente)] == \
        ["banco.conexoes", "banco.tamanho", *COMUNS]


def test_cobertura_conta_as_comuns_e_tira_o_nao_medido_por_desenho():
    componente = {"nome": "qdrant", "papel": "busca", "papel_origem": "declarado",
                  "origem": "processo:qdrant", "respostas": [
                      {"pergunta": "servico.ativo", "fonte": "ssh", "valor": "ativo"},
                      {"pergunta": "servico.desde", "fonte": "ssh", "valor": 3.0},
                      {"pergunta": "servico.reinicios", "sem_dados": True, "nao_publica": True,
                       "motivo": "processo sem gerenciador"},
                      {"pergunta": "servico.memoria", "sem_dados": True, "motivo": "ps falhou"}]}
    assert medir({"componentes": [componente]}) == {
        "perguntadas": 3, "respondidas": 2, "pct": 67,
        "mudos": [{"componente": "qdrant", "pergunta": "servico.memoria", "motivo": "ps falhou"}]}


class SemMetricas:
    ID = "promql_falso"

    def perguntar(self, pergunta, componente, contexto):
        return {"pergunta": pergunta, "sem_dados": True,
                "motivo": "o componente não declara `metricas_url` no alvos.toml"}


class DoHost:
    ID = "produto_falso"

    def perguntar(self, pergunta, componente, contexto):
        return {"pergunta": pergunta, "sem_dados": True, "explica_a_falta": True,
                "motivo": "leitura não declarada"}


def test_motivo_do_adaptador_de_host_vence_o_do_exporter_e_a_marca_nao_fica():
    componente = {"nome": "mariadb", "papel": "banco", "respostas": [], "achados": []}
    collect.responder(componente, {"timeout": 5}, [SemMetricas(), DoHost()], Prazo(30))
    assert [r["motivo"] for r in componente["respostas"]] == ["leitura não declarada"] * 2
    assert all("explica_a_falta" not in r for r in componente["respostas"])


def test_componente_declarado_no_host_recebe_as_comuns_pelo_ssh(monkeypatch):
    saidas = {**SAIDAS_PADRAO, "servico_unidade:mariadb.service": SHOW}
    monkeypatch.setattr("lib.runner.run_ssh", runner_falso(saidas))
    alvo = {"nome": "banco-01", "tipo": "host", "ssh_destino": "root@banco-01",
            "componente": [{"nome": "mariadb", "papel": "banco",
                            "origem": "unidade:mariadb.service"}]}
    contexto = {"timeout": 20, "http_timeout": 8, "orcamento": 120, "orcamento_urls": 120,
                "janela": "24h", "at": "2026-11-13T10:00:00Z"}
    registro = collect.coletar_alvo(alvo, host.coletar, contexto, adaptadores.todos())
    mariadb = next(c for c in registro["componentes"] if c["nome"] == "mariadb")
    ativo = next(r for r in mariadb["respostas"] if r["pergunta"] == "servico.ativo")
    assert ativo == {"pergunta": "servico.ativo", "fonte": "ssh", "valor": "ativo"}
