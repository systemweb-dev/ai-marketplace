"""Rodada só com cluster e endpoint: a referência de que um relatório sem host não muda (parte C)."""
from lib import remediacao
from tests.fixtures.relatorio_grande import _nos


def _resposta(pergunta, valor, fonte):
    return {"pergunta": pergunta, "valor": valor, "fonte": fonte}


def _componentes():
    return [
        {"nome": "loja_proxy", "papel": "entrada", "achados": [], "respostas": [
            _resposta("entrada.volume_na_janela", 125000, "promql:traefik")]},
        {"nome": "loja_fila", "papel": "fila", "achados": [], "respostas": [
            _resposta("fila.filas", [{"nome": "pedidos", "objeto": "pedidos@/", "prontas": 3,
                                      "consumidores": 2}], "admin_http:broker")]},
        {"nome": "loja_cache", "papel": "cache", "achados": [], "respostas": [
            _resposta("cache.memoria_usada", 52428800, "promql:redis")]},
        {"nome": "loja_api", "papel": "app", "achados": [], "respostas": [
            _resposta("app.cpu", 12.5, "promql:cadvisor"), _resposta("app.memoria", 268435456, "promql:cadvisor")]},
        {"nome": "loja_db", "papel": "banco", "achados": [], "respostas": [
            _resposta("banco.conexoes", 18, "promql:mysqld"), _resposta("banco.tamanho", 1073741824, "promql:mysqld")]},
        {"nome": "no-0", "papel": "maquina", "achados": [], "respostas": [
            _resposta("maquina.cpu", 35.0, "promql:node"), _resposta("maquina.memoria", 62.0, "promql:node"),
            _resposta("maquina.disco", 71.0, "promql:node")]},
    ]


def _achados():
    achados = [{"regra": "SEC_USER_ROOT", "objeto": "loja_api", "alvo": "loja", "severidade": "medium",
                "detalhe": "roda como root"},
               {"regra": "OPS_NO_HEALTHCHECK", "objeto": "loja_fila", "alvo": "loja", "severidade": "low",
                "detalhe": "sem healthcheck"}]
    for achado in achados:
        achado["como_resolver"] = remediacao.para(achado["regra"])
    return achados


def relatorio_docker():
    componentes = _componentes()
    servicos = [{"name": c["nome"], "replicas": "1/1", "tasks_failed": 0, "image": "img", "kind": "app"}
                for c in componentes if c["papel"] != "maquina"]
    docker = {"nome": "loja", "tipo": "docker", "onde": "context: loja", "saude": "🟢", "coletado": True,
              "dimensoes": {}, "fatos": {"services": servicos, "nodes": _nos()[:1]},
              "componentes": componentes, "achados": _achados(), "cobertura": {}, "analise": "",
              "nao_coletado": []}
    http = {"nome": "site", "tipo": "http", "onde": "https://site.exemplo", "saude": "🟢", "coletado": True,
            "dimensoes": {}, "fatos": {"codigo": 200}, "componentes": [], "achados": [], "cobertura": {},
            "analise": "", "nao_coletado": []}
    alvos = [docker, http]
    return {"schema_version": 3, "generated_at": "2026-11-01T10:00:00Z", "alvos": alvos,
            "inventario": [{"nome": a["nome"], "tipo": a["tipo"], "onde": a["onde"], "saude": a["saude"]}
                           for a in alvos],
            "aceites": [], "historico": {}, "resumo": "", "fortes": [], "fracos": [], "recomendacoes": []}
