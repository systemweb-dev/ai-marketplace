"""Dois servidores host com números fictícios: um com banco, busca e problemas, outro sem VPN."""
import copy

from lib import remediacao


def _r(pergunta, valor):
    return {"pergunta": pergunta, "valor": valor, "fonte": "ssh"}


def _servico(ativo, desde, reinicios, memoria):
    return [_r("servico.ativo", ativo), _r("servico.desde", desde), _r("servico.reinicios", reinicios),
            _r("servico.memoria", memoria)]


def _achado(regra, componente, severidade, detalhe, objeto=None):
    return {"regra": regra, "alvo": "banco-01", "componente": componente, "objeto": objeto or componente,
            "severidade": severidade, "detalhe": detalhe, "como_resolver": remediacao.para(regra)}


def alvo_host_banco():
    maquina = {"nome": "banco-01", "papel": "maquina", "achados": [], "respostas": [
        _r("maquina.cpu", 24.0), _r("maquina.memoria", 78.0), _r("maquina.disco", 93.0),
        _r("maquina.carga", 24.0), _r("maquina.desde_o_boot", 41.0)]}
    mariadb = {"nome": "mariadb", "papel": "banco", "produto": "mariadb", "backup_max_dias": 2,
               "achados": [], "respostas": [
                   *_servico("ativo", 41.0, 0, 2147483648),
                   _r("banco.conexoes", 37), _r("banco.uso_de_conexoes", 24.7), _r("banco.tamanho", 9663676416),
                   _r("banco.tamanho_por_banco", [{"nome": "loja", "bytes": 7516192768},
                                                  {"nome": "erp", "bytes": 1610612736},
                                                  {"nome": "mysql", "bytes": 34003200},
                                                  {"nome": "information_schema", "bytes": None}]),
                   _r("banco.consultas_lentas", 12), _r("banco.binlog", [{"nome": "binlog.000041", "bytes": 1048576}]),
                   _r("banco.backup_idade", 5)]}
    qdrant = {"nome": "qdrant", "papel": "busca", "produto": "qdrant", "achados": [], "respostas": [
        *_servico("ativo", 12.0, 1, 805306368),
        _r("busca.colecoes", [{"nome": "docs", "pontos": 120400, "status": "green"},
                              {"nome": "faq", "pontos": 3100, "status": "yellow"},
                              {"nome": "vazia", "pontos": 0, "status": "green"}])]}
    redis = {"nome": "redis", "papel": "cache", "produto": "redis", "achados": [],
             "respostas": _servico("failed", None, 7, None)}
    pg = {"nome": "pg", "papel": "banco", "produto": "postgres", "achados": [], "respostas": []}
    api = {"nome": "loja-api", "papel": "app", "achados": [], "respostas": _servico("ativo", 3.0, 0, 314572800)}
    achados = [_achado("backup_atrasado", "mariadb", "high", "backup mais novo com 5 dias; o limite é 2"),
               _achado("servico_reiniciando", "redis", "medium", "7 reinícios registrados pelo gerenciador do serviço"),
               _achado("servico_declarado_ausente", "pg", "high", "declarado no alvos.toml e não encontrado"),
               _achado("disco_quase_cheio", "banco-01", "high", "93% do disco em uso", objeto="banco-01")]
    return {"nome": "banco-01", "tipo": "host", "onde": "ssh: banco-01", "saude": "🟡", "coletado": True,
            "dimensoes": {}, "cobertura": {}, "analise": "",
            "fatos": {"usuario": "root", "kernel": "Linux 6.1.0-18-amd64",
                      "sistema": "Debian GNU/Linux 12 (bookworm)",
                      "acesso": "Acesso com a identidade SSH de quem executou a auditoria (root).",
                      "descobertos": [{"produto": "postgres", "origem": "unidade:postgresql.service"}]},
            "componentes": [maquina, mariadb, qdrant, redis, pg, api], "achados": achados,
            "nao_coletado": [{"valor": None, "motivo": "descoberto e não declarado: postgres "
                                                       "(unidade:postgresql.service) — rode `configurar.py "
                                                       "descobrir --alvo banco-01`"}]}


def alvo_host_sem_vpn():
    return {"nome": "cache-02", "tipo": "host", "onde": "ssh: cache-02", "saude": "sem dados", "coletado": True,
            "dimensoes": {}, "cobertura": {}, "analise": "", "fatos": {}, "componentes": [], "achados": [],
            "nao_coletado": [{"valor": None, "motivo": "não abri a sessão para cache-02 (a VPN está ligada?)"}]}


def relatorio_com_hosts(base=None):
    r = copy.deepcopy(base) if base else {
        "schema_version": 3, "generated_at": "2026-11-14T09:12:00Z", "alvos": [], "inventario": [],
        "aceites": [], "historico": {}, "resumo": "", "fortes": [], "fracos": [], "recomendacoes": []}
    for alvo in (alvo_host_banco(), alvo_host_sem_vpn()):
        r["alvos"].append(alvo)
        r["inventario"].append({"nome": alvo["nome"], "tipo": "host", "onde": alvo["onde"], "saude": alvo["saude"]})
    r.pop("nota_geral", None)          # a nota recalcula com os hosts
    return r
