"""Rota do proxy ligada ao domínio e à stack: o bloco Sites e a coluna Resposta."""
from lib import blocos as b
from lib.adaptadores import promql
from lib.dados_blocos import dados_do_papel, medidas_por_stack

ACESSOS = [{"nome": "loja-web@swarm", "acessos": 90, "erros": 2, "resposta": 120},
           {"nome": "painel@swarm", "acessos": 50, "erros": 0, "resposta": 40},
           {"nome": "sem-regra@swarm", "acessos": 10, "erros": 0, "resposta": 30},
           {"nome": "ping@internal", "acessos": 5, "erros": None, "resposta": 1}]
SERVICOS = [{"name": "loja_web", "routing_labels": {
                "traefik.enable": "true",
                "traefik.http.routers.loja-web.rule": "Host(`loja.example.com`) && PathPrefix(`/app`)"}},
            {"name": "adm_painel", "routing_labels": {
                "traefik.http.routers.painel.rule": "PathPrefix(`/painel`)"}},
            {"name": "avulso", "routing_labels": {}}]


def _alvo(nome="c", servicos=None, respostas=None):
    respostas = ACESSOS if respostas is None else respostas
    return {"nome": nome, "fatos": {"services": SERVICOS if servicos is None else servicos},
            "componentes": [{"nome": "proxy", "papel": "entrada", "respostas": [
                {"pergunta": "entrada.volume_na_janela", "fonte": f"promql:{nome}", "valor": 155},
                {"pergunta": "entrada.por_servico", "fonte": f"promql:{nome}", "valor": respostas}]}]}


def _servicos(*alvos):
    return [s for i in dados_do_papel("entrada", list(alvos))["itens"] for s in i["servicos"]]


def test_rota_vira_dominio_e_quem_nao_tem_dominio_mostra_o_nome_da_rota():
    assert [s["nome"] for s in _servicos(_alvo())] == [
        "loja.example.com", "painel", "sem-regra", "ping"]
    assert _servicos(_alvo())[0]["acessos"] == 90


def test_varios_dominios_saem_todos_e_em_ordem_estavel():
    regras = ["Host(`b.example.com`) || Host(`a.example.com`)", "Host(`b.example.com`, `a.example.com`)"]
    for regra in regras:
        servicos = [{"name": "x", "routing_labels": {"traefik.http.routers.r.rule": regra}}]
        nomes = [s["nome"] for s in _servicos(_alvo(servicos=servicos, respostas=[{"nome": "r@swarm"}]))]
        assert nomes == ["a.example.com · b.example.com"]


def test_regra_que_exclui_dominio_nao_o_afirma():
    servicos = [{"name": "x", "routing_labels": {
        "traefik.http.routers.r.rule": "PathPrefix(`/`) && !Host(`fora.example.com`)"}}]
    assert [s["nome"] for s in _servicos(_alvo(servicos=servicos, respostas=[{"nome": "r@swarm"}]))] == ["r"]


def test_rota_de_um_alvo_nao_pega_o_dominio_do_outro():
    outro = [{"name": "b_web", "routing_labels": {"traefik.http.routers.loja-web.rule": "Host(`outro.example.com`)"}}]
    nomes = {s["nome"] for s in _servicos(_alvo("a"), _alvo("b", servicos=outro))}
    assert {"loja.example.com", "outro.example.com"} <= nomes


def test_a_resposta_original_nao_e_alterada():
    alvo = _alvo()
    dados_do_papel("entrada", [alvo])
    assert alvo["componentes"][0]["respostas"][1]["valor"][0]["nome"] == "loja-web@swarm"


def test_servicos_indisponiveis_nao_quebram_a_juncao():
    alvo = _alvo()
    alvo["fatos"]["services"] = {"status": "n/a"}
    assert _servicos(alvo)[0]["nome"] == "loja-web"
    assert medidas_por_stack([alvo]) == {}


def test_titulo_e_sites_com_dominio_e_servicos_web_sem_nenhum():
    com = b.render_bloco("entrada", dados_do_papel("entrada", [_alvo()]))
    assert "<h3>Sites</h3>" in com and "loja.example.com" in com and "Serviços web" not in com
    sem = b.render_bloco("entrada", dados_do_papel("entrada", [_alvo(servicos=[])]))
    assert "<h3>Serviços web</h3>" in sem and "Sites" not in sem and "<b>loja-web</b>" in sem


def test_top_15_vale_depois_da_juncao():
    respostas = [{"nome": f"r{i:02}@swarm", "acessos": 100 - i, "erros": 0} for i in range(17)]
    respostas.append({"nome": "raro@swarm", "acessos": 1, "erros": 3})
    html = b.render_bloco("entrada", dados_do_papel("entrada", [_alvo(respostas=respostas)]))
    assert "<b>r14</b>" in html and "<b>r15</b>" not in html and "<b>raro</b>" in html


def test_resposta_vai_para_a_stack_do_servico_que_declara_a_rota():
    assert medidas_por_stack([_alvo()]) == {"loja": {"resposta": 120}, "adm": {"resposta": 40}}


def test_duas_rotas_da_mesma_stack_ficam_com_a_pior_resposta():
    servicos = [{"name": "loja_web", "routing_labels": {
        "traefik.http.routers.a.rule": "Host(`a.example.com`)",
        "traefik.http.routers.b.rule": "Host(`b.example.com`)"}}]
    respostas = [{"nome": "a@swarm", "resposta": 300}, {"nome": "b@swarm", "resposta": 2}]
    assert medidas_por_stack([_alvo(servicos=servicos, respostas=respostas)]) == {"loja": {"resposta": 300}}


def test_a_coleta_junta_os_campos_pela_etiqueta_router(monkeypatch):
    """Dados fictícios no lugar do Prometheus: o caminho é o de produção até o item."""
    from lib import catalogo
    consultas = []

    def falso(base, query, timeout, at=None):
        consultas.append(query)
        if "duration" in query:
            return [{"metric": {"router": "a@swarm"}, "value": [0, "12.6"]}]
        if "5.." in query:
            return [{"metric": {"router": "a@swarm"}, "value": [0, "3"]}]
        return [{"metric": {"router": "b@swarm"}, "value": [0, "7"]},
                {"metric": {"router": "a@swarm"}, "value": [0, "7"]}]

    monkeypatch.setattr(promql, "_consultar", falso)
    traefik = next(f for f in catalogo.familias() if f["familia"] == "traefik")
    declarada = next(p for p in traefik["pergunta"] if p["id"] == "entrada.por_servico")
    resposta = promql._lista_de_campos("entrada.por_servico", declarada, "http://x", 'job="t"',
                                       {"timeout": 1, "janela": "24h"}, "promql:traefik")
    assert resposta["valor"] == [{"nome": "a@swarm", "acessos": 7, "erros": 3, "resposta": 12},
                                 {"nome": "b@swarm", "acessos": 7, "erros": None, "resposta": None}]
    assert all('job="t"}[24h]' in q for q in consultas)
