import pathlib
import re

import pytest

import lib.blocos as b
from lib.dados_blocos import dados_do_papel

RAIZ = pathlib.Path(__file__).resolve().parents[1]
TPL = RAIZ / "assets" / "report-template" / "template_v3.html"
PAPEIS = ["fila", "entrada", "banco", "cache", "maquinas", "consumo", "falhas"]


@pytest.mark.parametrize("papel", ["fila", "entrada", "banco", "cache", "maquinas", "consumo", "falhas"])
def test_bloco_sem_dado_diz_nao_medido_e_nao_mostra_zero(papel):
    html = b.render_bloco(papel, {"motivo": "sem exporter"})
    assert "Não medido" in html and ">0<" not in html


def test_fila_parada_vem_primeiro_com_o_saldo():
    html = b.render_bloco("fila", {"filas": [
        {"nome": "ok", "prontas": 1, "consumidores": 2, "entrada": 5, "saida": 5},
        {"nome": "emails", "prontas": 900, "consumidores": 0, "entrada": 3, "saida": 0}]})
    assert html.index("emails") < html.index(">ok<") and "+3/min" in html


@pytest.mark.parametrize("dias", [-1, -0.5, float("inf"), float("-inf")])
def test_disco_que_nao_enche_e_estavel_sem_numero(dias):
    html = b.render_bloco("maquinas", {"itens": [{"nome": "m", "disco": 40, "dias": dias}]})
    assert ">estável<" in html
    assert "inf" not in html.replace("bl-", "") and "-1" not in html and "dias" not in html


@pytest.mark.parametrize("dias,texto", [
    (9.4, "enche em 9 dias"), (1, "enche em 1 dia"), (0.4, "enche em menos de 1 dia"),
    (0, "enche em menos de 1 dia")])
def test_disco_em_alta_mostra_a_previsao(dias, texto):
    html = b.render_bloco("maquinas", {"itens": [{"nome": "m", "disco": 40, "dias": dias}]})
    assert f">{texto}<" in html and "estável" not in html


def test_previsao_sem_medida_fica_sem_dado():
    html = b.render_bloco("maquinas", {"itens": [{"nome": "m", "disco": 40, "dias": None}]})
    assert "Previsão do disco" in html and "sem dado" in html and "estável" not in html


def test_papel_sem_bloco_usa_tabela_generica():
    assert 'class="bl-tb"' in b.render_bloco("storage", {"uso": "41%"})


def test_adaptador_junta_as_tres_perguntas_e_converte_para_minuto():
    alvo = {"componentes": [{"nome": "mq", "papel": "fila", "respostas": [
        {"pergunta": "fila.filas", "valor": [{"objeto": "e@/", "nome": "e", "prontas": 9, "consumidores": 0}]},
        {"pergunta": "fila.taxa_entrada_saida", "valor": [{"objeto": "e@/", "entrada": 0.5, "saida": 0.0}]}]}]}
    assert dados_do_papel("fila", [alvo])["filas"] == [
        {"nome": "e", "prontas": 9, "consumidores": 0, "entrada": 30, "saida": 0}]


def test_adaptador_sem_componente_informa_o_motivo():
    assert dados_do_papel("banco", [{"componentes": []}])["motivo"]


def test_todos_os_blocos_sao_importados_sozinhos():
    assert set(PAPEIS) <= set(b.BLOCOS)
    fonte = (RAIZ / "scripts" / "lib" / "blocos" / "__init__.py").read_text(encoding="utf-8")
    assert "ModuleNotFoundError" not in fonte


def test_fila_ociosa_fica_sem_dado_e_nao_vira_saldo_zero():
    alvo = {"componentes": [{"nome": "mq", "papel": "fila", "respostas": [
        {"pergunta": "fila.filas", "valor": [{"nome": "e", "prontas": 0, "consumidores": 1}]},
        {"pergunta": "fila.taxa_entrada_saida", "valor": [{"nome": "e", "entrada": None, "saida": None}]}]}]}
    dados = dados_do_papel("fila", [alvo])
    assert dados["filas"][0]["entrada"] is None and dados["filas"][0]["saida"] is None
    html = b.render_bloco("fila", dados)
    assert "sem dado" in html and "0/min" not in html


def test_taxa_de_uma_fila_nao_vaza_para_outra_quando_nao_ha_objeto():
    alvo = {"componentes": [{"nome": "mq", "papel": "fila", "respostas": [
        {"pergunta": "fila.filas", "valor": [{"nome": "a", "prontas": 1, "consumidores": 1},
                                             {"nome": "b", "prontas": 1, "consumidores": 1}]},
        {"pergunta": "fila.taxa_entrada_saida", "valor": [{"nome": "a", "entrada": 1, "saida": 1},
                                                          {"nome": "b", "entrada": 2, "saida": 2}]}]}]}
    assert [f["entrada"] for f in dados_do_papel("fila", [alvo])["filas"]] == [60, 120]


def test_consumidor_desconhecido_nao_declara_fila_parada():
    html = b.render_bloco("fila", {"filas": [
        {"nome": "e", "prontas": 5, "consumidores": None, "entrada": 1, "saida": 1}]})
    assert "Parada" not in html and "sem dado" in html


@pytest.mark.parametrize("papel, dados", [
    ("banco", {"itens": [{"nome": "x", "conexoes": None, "tamanho": None}]}),
    ("cache", {"itens": [{"nome": "x", "memoria": None, "evictions": None, "acerto": None}]}),
    ("maquinas", {"itens": [{"nome": "x", "cpu": None, "memoria": None, "disco": None}]}),
    ("consumo", {"itens": [{"nome": "x", "cpu": None, "memoria": None}]}),
    ("entrada", {"itens": [{"nome": "x", "volume": None, "status": None, "latencia": None}]}),
    ("falhas", {"itens": [{"cenario": None, "consequencia": None}]}),
    ("storage", {"uso": None}),
])
def test_none_vira_sem_dado_e_nunca_zero(papel, dados):
    html = b.render_bloco(papel, dados)
    assert "sem dado" in html
    assert not re.search(r">\s*0(?:[,.]0)?\s*(?:%|ms|GB|B\b)?\s*<", html)
    assert "None" not in html


def test_zero_medido_continua_zero():
    html = b.render_bloco("cache", {"itens": [{"nome": "x", "memoria": 0, "evictions": 0, "acerto": 0}]})
    assert "0%" in html and "sem evicções" in html


def test_consumo_ordena_por_cpu_e_desempata_por_nome():
    html = b.render_bloco("consumo", {"itens": [
        {"nome": "z", "cpu": 5, "memoria": 1}, {"nome": "b", "cpu": 9, "memoria": 1},
        {"nome": "a", "cpu": 9, "memoria": 1}, {"nome": "n", "cpu": None, "memoria": 1}]})
    assert [html.index(f"<b>{n}</b>") for n in "abzn"] == sorted(html.index(f"<b>{n}</b>") for n in "abzn")


def test_entrada_mostra_status_latencia_e_top_15_sem_perder_quem_teve_erro():
    servicos = [{"nome": f"s{i:02}", "acessos": 100 - i, "erros": 0, "resposta": 10} for i in range(16)]
    servicos.append({"nome": "raro", "acessos": 1, "erros": 2, "resposta": None})
    html = b.render_bloco("entrada", {"itens": [{"nome": "borda", "volume": 1000, "latencia": 184,
                                                 "status": [{"chave": "200", "valor": 900},
                                                            {"chave": "404", "valor": 90},
                                                            {"chave": "500", "valor": 10}],
                                                 "servicos": servicos}]})
    assert "90,0% ok" in html and "9,0% 4xx" in html and "1,0% 5xx" in html and "184 ms" in html
    assert "s14" in html and "s15" not in html and "raro" in html


def test_valor_vindo_de_fora_e_escapado():
    html = b.render_bloco("fila", {"filas": [
        {"nome": "<x>", "prontas": 1, "consumidores": 1, "entrada": 1, "saida": 1}]})
    assert "<x>" not in html


def test_css_dos_blocos_quebra_linha_em_vez_de_cortar():
    html = TPL.read_text(encoding="utf-8")
    css = "\n".join(l for l in html.splitlines() if l.lstrip().startswith((".bl-", "@media")) or "bl-" in l)
    assert "text-overflow" not in css and "nowrap" not in css.split(".bl-tag-ok")[0]
    td = re.search(r"\.bl-tb td\{([^}]*)\}", html).group(1)
    assert "white-space:normal" in td and "overflow-wrap:anywhere" in td


@pytest.mark.parametrize("vazio", [[], {}])
def test_resposta_vazia_nao_conta_como_medida(vazio):
    alvo = {"componentes": [{"nome": "proxy", "papel": "entrada", "respostas": [
        {"pergunta": "entrada.distribuicao_de_status", "valor": vazio}]}]}
    dados = dados_do_papel("entrada", [alvo])
    assert dados == {"motivo": "sem fonte medida para este tipo"}
    html = b.render_bloco("entrada", dados)
    assert "Não medido" in html and "medidos" not in html


def test_lista_vazia_nao_derruba_o_que_foi_medido_de_verdade():
    alvo = {"componentes": [{"nome": "proxy", "papel": "entrada", "respostas": [
        {"pergunta": "entrada.distribuicao_de_status", "valor": []},
        {"pergunta": "entrada.volume_na_janela", "valor": 0}]}]}
    assert len(dados_do_papel("entrada", [alvo])["itens"]) == 1


@pytest.mark.parametrize("cpu, esperado", [(250, "2,5 cores"), (140, "1,4 cores"), (90, "0,9 cores"),
                                           (100, "1 core"), (0, "0 cores"), (4, "&lt; 0,1 cores")])
def test_consumo_mostra_cpu_em_nucleos(cpu, esperado):
    html = b.render_bloco("consumo", {"itens": [{"nome": "x", "cpu": cpu, "memoria": 1}]})
    assert f'<span class="bl-v">{esperado}</span>' in html
    assert f"{cpu}%" not in html.replace('width:100%', "").replace('width:0%', "")


@pytest.mark.parametrize("n, esperado", [(0, "0"), (999, "999"), (1000, "1 mil"), (1500, "1,5 mil"),
                                         (999_949, "999,9 mil"), (999_999, "1 mi"), (1_000_000, "1 mi"),
                                         (999_999_999, "1 bi"), (1_000_000_000, "1 bi"), (-999_999, "-1 mi")])
def test_humano_nos_limites_nunca_diz_1000_mil(n, esperado):
    from lib.html_comum import humano
    assert humano(n) == esperado


@pytest.mark.parametrize("volume, esperado", [(1, "1 acesso"), (500, "500 acessos"), (999, "999 acessos"),
                                              (1000, "1 mil de acessos"), (999_999, "1 mi de acessos"),
                                              (1_000_000, "1 mi de acessos"), (1_200_000, "1,2 mi de acessos")])
def test_acessos_so_levam_de_depois_de_mil_ou_mi(volume, esperado):
    html = b.render_bloco("entrada", {"itens": [{"nome": "x", "volume": volume}]})
    assert f"<span>{esperado}</span>" in html


def fila(**extra):
    return {"nome": "e", "prontas": 0, "consumidores": 1, "entrada": None, "saida": None, **extra}


def test_fila_ociosa_e_neutra_e_nao_amarela():
    html = b.render_bloco("fila", {"filas": [fila()]})
    assert "Ociosa" in html and "1 ociosa" in html
    assert "bl-tag-neutro" in html and "bl-q-neutro" in html and "warn" not in html


def test_fila_ociosa_vai_para_o_fim_e_se_pluraliza():
    html = b.render_bloco("fila", {"filas": [fila(nome="a"), fila(nome="c"),
                                             fila(nome="b", prontas=None)]})
    assert html.index("<b>b</b>") < html.index("<b>a</b>") and "2 ociosas" in html


@pytest.mark.parametrize("extra", [{"prontas": None}, {"prontas": 3}, {"entrada": 1}, {"saida": 1},
                                   {"nao_confirmadas": 8}, {"ritmo_nao_medido": True}])
def test_o_que_nao_e_ociosa_nao_se_diz_ociosa(extra):
    assert "Ociosa" not in b.render_bloco("fila", {"filas": [fila(**extra)]})


@pytest.mark.parametrize("papel", ["storage", "busca", "observabilidade"])
def test_papel_sem_bloco_devolve_o_motivo(papel):
    assert dados_do_papel(papel, [{"componentes": []}]) == {"motivo": "sem fonte medida para este tipo"}


def test_um_item_sai_no_singular_nos_resumos():
    from lib.blocos import render_bloco as rb
    assert "1 medido<" in rb("banco", {"itens": [{"nome": "a", "conexoes": 1}]})
    assert "1 medido<" in rb("cache", {"itens": [{"nome": "a", "acerto": 90}]})
    assert "1 medido<" in rb("entrada", {"itens": [{"nome": "a", "volume": 1}]})
    assert "1 medida<" in rb("maquinas", {"itens": [{"nome": "a", "cpu": 1}]})
    assert "1 apontado<" in rb("falhas", {"itens": [{"cenario": "a", "consequencia": "b"}]})
    assert "2 medidos<" in rb("banco", {"itens": [{"nome": "a"}, {"nome": "b"}]})


def _maquina(nome, respostas):
    return {"nome": nome, "papel": "maquina", "respostas": respostas}


def test_no_sem_medida_aparece_com_sem_dado():
    medido = _maquina("db-1", [{"pergunta": "maquina.cpu", "valor": 40, "fonte": "promql:x"}])
    mudo = _maquina("web-1", [{"pergunta": "maquina.cpu", "sem_dados": True, "motivo": "x"}])
    dados = dados_do_papel("maquinas", [{"componentes": [mudo, medido]}])
    assert [i["nome"] for i in dados["itens"]] == ["db-1", "web-1"]
    html = b.render_bloco("maquinas", dados)
    assert "web-1" in html and "sem dado" in html
    assert "1 medida" in html and "2 medidas" not in html


def test_sem_nenhum_no_medido_o_bloco_explica_por_que():
    mudo = _maquina("web-1", [{"pergunta": "maquina.cpu", "sem_dados": True, "motivo": "x"}])
    assert dados_do_papel("maquinas", [{"componentes": [mudo]}]) == {"motivo": "sem fonte medida para este tipo"}


def test_servico_sem_medida_continua_fora_do_consumo():
    medido = {"nome": "a", "papel": "app", "respostas": [{"pergunta": "app.cpu", "valor": 5, "fonte": "f"}]}
    mudo = {"nome": "b", "papel": "app", "respostas": []}
    assert [i["nome"] for i in dados_do_papel("consumo", [{"componentes": [medido, mudo]}])["itens"]] == ["a"]


def test_sem_ritmo_a_contagem_ainda_diz_o_estado_da_fila():
    filas = [{"nome": "a", "prontas": 3, "nao_confirmadas": 0, "consumidores": 2, "entrada": None,
              "saida": None, "ritmo_nao_medido": True},
             {"nome": "b", "prontas": 0, "nao_confirmadas": 0, "consumidores": 1, "entrada": None,
              "saida": None, "ritmo_nao_medido": True}]
    html = b.render_bloco("fila", {"filas": filas})
    assert "1 com consumidor · 1 vazia" in html and "Sem dado" not in html
