"""A capa quando o agente não escreveu recomendação e a linha do que não foi medido."""
import pytest

import build_report as br
from lib.adaptadores import promql
from lib.blocos import render_bloco
from lib.capa import render_capa
from lib.coletores.docker import USO_POR_NO
from lib.dados_blocos import nao_coletado_vigente
from lib.regras import REGRAS
from tests.test_build_report_v3 import relatorio

OBSOLETO = {"valor": None, "motivo": f"{USO_POR_NO}: requer Prometheus/cAdvisor (capacidade é reportada)"}
SEM_LIGACAO = "o exporter x cobre vários componentes e nenhum valor da etiqueta casa com o nome"
SEM_EXPORTER = "os exporters x e y não expõem o dado desta pergunta"
SEM_SENHA = "o componente 'f' declara senha_env='S', mas essa variável não está no ambiente"


def _achado(regra, severidade, objeto="a"):
    return {"regra": regra, "severidade": severidade, "objeto": objeto}


def _capa(achados, recomendacoes=()):
    return render_capa({"achados": achados, "recomendacoes": list(recomendacoes)}, None, "", [])


def _itens(html):
    return html.split('class="bl-prio"', 1)[1].split("</ol>", 1)[0].split("<li>")[1:]


# --- 1. prioridades sem recomendação
def test_sem_recomendacao_a_capa_usa_os_problemas_mais_graves():
    html = _capa([_achado("OPS_NO_LIMITS", "low"), _achado("SEC_USER_ROOT", "medium", "a"),
                  _achado("SEC_USER_ROOT", "medium", "b"), _achado("OPS_NODE_DOWN", "high")])
    primeiro, segundo, terceiro = _itens(html)
    assert "Nó fora do ar" in primeiro and "bl-nivel-crit" in primeiro and ">Alto<" in primeiro
    assert ">Infraestrutura<" in primeiro and "1 ocorrência." in primeiro
    assert "Roda como root" in segundo and ">Médio<" in segundo and ">Segurança<" in segundo
    assert "2 ocorrências." in segundo and "SEC_USER_ROOT" not in html
    assert "Sem limite de CPU/memória" in terceiro and ">Baixo<" in terceiro


def test_mesma_gravidade_vem_quem_mais_ocorre_e_para_em_cinco():
    regras = ("OPS_NO_LIMITS", "OPS_NO_HEALTHCHECK", "OPS_ENGINE_DRIFT", "OPS_NODE_DRAIN",
              "OPS_TLS_EXPIRED", "OPS_TASK_FAILING")
    achados = [_achado(r, "low") for r in regras] + [_achado("OPS_ENGINE_DRIFT", "low", "b")]
    itens = _itens(_capa(achados))
    assert len(itens) == 5 and "Versões de engine divergentes" in itens[0]


def test_recomendacao_vem_antes_e_o_problema_completa_as_vagas():
    recs = [{"titulo": "Trocar a imagem", "porque": "motivo", "impacto": "alto", "alvo": "x", "regra": "SEC_USER_ROOT"}]
    itens = _itens(_capa([_achado("SEC_USER_ROOT", "medium"), _achado("OPS_NODE_DOWN", "high")], recs))
    assert len(itens) == 2 and "Trocar a imagem" in itens[0] and "Nó fora do ar" in itens[1]


def test_cinco_recomendacoes_nao_deixam_vaga_para_problema():
    recs = [{"titulo": f"R{i}", "impacto": "alto"} for i in range(5)]
    assert "Nó fora do ar" not in _capa([_achado("OPS_NODE_DOWN", "high")], recs)


def test_esperado_e_informativo_nao_viram_prioridade():
    html = _capa([_achado("SEC_DOCKER_SOCK_EXPECTED", "low"), _achado("OPS_JOB_COMPLETED", "low"),
                  {**_achado("OPS_NO_LIMITS", "low"), "esperada": True}, _achado("OPS_NODE_DRAIN", "info")])
    assert "O que fazer primeiro" not in html


@pytest.mark.parametrize("regra, quem", [("SEC_PRIVILEGED", "Segurança"), ("sem_tls", "Segurança"),
                                         ("certificado_vencendo", "Segurança"),
                                         ("fila_sem_consumidor", "Aplicação"),
                                         ("http_fora_do_ar", "Infraestrutura"),
                                         ("OPS_TASK_FAILING", "Infraestrutura")])
def test_quem_age_sai_da_categoria(regra, quem):
    assert f">{quem}<" in _capa([_achado(regra, "high")])


def test_toda_regra_nao_esperada_tem_rotulo_legivel():
    for regra, dados in REGRAS.items():
        if not dados["esperada"]:
            assert regra not in _capa([_achado(regra, "high")])


def test_relatorio_sem_recomendacao_preenche_a_capa():
    r = relatorio()
    r["recomendacoes"] = []
    r["alvos"][0]["achados"] = [dict(_achado("OPS_NODE_DOWN", "high"), alvo=r["alvos"][0]["nome"])]
    assert "O que fazer primeiro" in br.render_html_v3(r)


# --- 2. linha do "Não medido"
def _alvo(papeis, mudos, **extra):
    return {"nome": "alvo", "componentes": [{"nome": n, "papel": p} for n, p in papeis.items()],
            "cobertura": {"mudos": mudos}, **extra}


def _mudo(componente, motivo=SEM_LIGACAO, pergunta="p"):
    return {"componente": componente, "pergunta": pergunta, "motivo": motivo}


def test_nao_medido_agrupa_por_categoria_na_ordem_dos_papeis():
    alvo = _alvo({"a1": "app", "a2": "app", "b": "banco", "c": "cache", "f": "fila"},
                 [_mudo(n) for n in ("a1", "a2", "b", "c", "f")])
    assert br._faltou([alvo]) == ["filas", "bancos", "cache", "2 serviços"]


def test_um_servico_vai_no_singular_e_duas_perguntas_contam_uma_vez():
    alvo = _alvo({"a": "app"}, [_mudo("a", pergunta="p1"), _mudo("a", pergunta="p2")])
    assert br._faltou([alvo]) == ["1 serviço"]


def test_o_mesmo_nome_em_dois_alvos_sao_dois_servicos():
    alvos = [dict(_alvo({"a": "app"}, [_mudo("a")]), nome=n) for n in ("um", "dois")]
    assert br._faltou(alvos) == ["2 serviços"]


def test_papel_nao_provado_nao_e_medida_que_faltou():
    alvo = _alvo({"a": "app"}, [_mudo("a", "papel não provado", "<identidade>")])
    assert br._faltou([alvo]) == [] and br._motivo_do_que_faltou([alvo]) is None


@pytest.mark.parametrize("motivo, curto", [
    (SEM_LIGACAO, "a métrica não identifica o serviço"), (SEM_EXPORTER, "não há exporter ligado"),
    (SEM_SENHA, "falta a senha no ambiente"), ("o componente não declara `metricas_url` no alvos.toml", "não há fonte declarada"),
    ("a fonte de métrica não respondeu", "a fonte não respondeu"), ("orçamento do alvo esgotado", "o tempo de coleta acabou"),
    ("outra coisa qualquer", "a fonte não trouxe o dado")])
def test_motivo_em_poucas_palavras(motivo, curto):
    assert br._motivo_do_que_faltou([_alvo({"a": "app"}, [_mudo("a", motivo)])]) == curto


def test_motivo_mais_comum_conta_componente_e_nao_pergunta():
    mudos = [_mudo("a", SEM_LIGACAO, p) for p in "123"] + [_mudo(n, SEM_EXPORTER) for n in ("b", "c")]
    alvo = _alvo({"a": "app", "b": "banco", "c": "cache"}, mudos)
    assert br._motivo_do_que_faltou([alvo]) == "não há exporter ligado"


def test_a_linha_sai_como_no_mockup():
    html = render_capa({"motivo_do_que_faltou": "não há exporter ligado"}, None, "", ["bancos", "cache"])
    assert ("<b>Não medido:</b> bancos e cache. Motivo mais comum: não há exporter ligado. "
            "Isso não significa") in html


def test_a_linha_junta_quatro_categorias_sem_cortar():
    assert "filas, bancos, cache e 11 serviços. Isso" in render_capa(
        {}, None, "", ["filas", "bancos", "cache", "11 serviços"])


# --- 3. sites
def _site(**campos):
    servico = {"nome": "loja.exemplo.invalido", "site": True, **campos}
    return render_bloco("entrada", {"itens": [{"nome": "proxy", "volume": 1, "servicos": [servico]}]})


def _celula_de_erros(html):
    return html.split("<tbody>", 1)[1].split("<td", 3)[3].split("</td>", 1)[0]


def test_rota_medida_sem_serie_5xx_mostra_nenhum():
    assert "nenhum" in _celula_de_erros(_site(acessos=100, resposta=20))


def test_acessos_nao_medidos_continua_sem_dado():
    assert "sem dado" in _celula_de_erros(_site(resposta=20))


def test_consulta_de_erros_que_falhou_nao_vira_nenhum():
    assert "sem dado" in _celula_de_erros(_site(acessos=100, nao_respondeu=["erros"]))


def test_erro_medido_continua_o_numero():
    assert "7" in _celula_de_erros(_site(acessos=100, erros=7))


def test_lista_de_campos_marca_o_campo_cuja_consulta_falhou(monkeypatch):
    respostas = {"acessos": [{"metric": {"router": "r"}, "value": [0, "5"]}], "erros": None}
    monkeypatch.setattr(promql, "_consultar", lambda base, query, *_: respostas[query])
    declarada = {"chave": "router", "ordenar_por": "acessos", "desempate": "nome",
                 "campo": [{"nome": "acessos", "query": "acessos"}, {"nome": "erros", "query": "erros"}]}
    resposta = promql._lista_de_campos("p", declarada, "http://x", "", {"timeout": 1}, "fonte")
    assert resposta["valor"][0]["nao_respondeu"] == ["erros"]


def test_serie_ausente_nao_marca_falha(monkeypatch):
    respostas = {"acessos": [{"metric": {"router": "r"}, "value": [0, "5"]}], "erros": []}
    monkeypatch.setattr(promql, "_consultar", lambda base, query, *_: respostas[query])
    declarada = {"chave": "router", "ordenar_por": "acessos", "desempate": "nome",
                 "campo": [{"nome": "acessos", "query": "acessos"}, {"nome": "erros", "query": "erros"}]}
    resposta = promql._lista_de_campos("p", declarada, "http://x", "", {"timeout": 1}, "fonte")
    assert "nao_respondeu" not in resposta["valor"][0]


# --- 4. nao_coletado obsoleto
def _maquina(nome, *perguntas):
    return {"nome": nome, "papel": "maquina", "respostas": [{"pergunta": p, "valor": 1} for p in perguntas]}


def _com_nos(*maquinas, nos=1):
    return {"nome": "alvo", "nao_coletado": [OBSOLETO, {"valor": None, "motivo": "outro motivo"}],
            "componentes": list(maquinas), "fatos": {"nodes": [{"hostname": str(i)} for i in range(nos)]}}


def test_maquinas_medidas_tiram_so_o_texto_obsoleto():
    alvo = _com_nos(_maquina("n", "maquina.cpu", "maquina.memoria"))
    assert [n["motivo"] for n in nao_coletado_vigente(alvo)] == ["outro motivo"]


@pytest.mark.parametrize("alvo", [
    _com_nos(),
    _com_nos(_maquina("n", "maquina.cpu")),
    _com_nos(_maquina("n", "maquina.cpu", "maquina.memoria"), nos=2),
    _com_nos({"nome": "n", "papel": "maquina", "respostas": [
        {"pergunta": "maquina.cpu", "sem_dados": True}, {"pergunta": "maquina.memoria", "sem_dados": True}]}),
])
def test_maquina_sem_medida_mantem_o_texto(alvo):
    assert OBSOLETO in nao_coletado_vigente(alvo)


def test_texto_obsoleto_some_das_pendencias_e_da_linha_da_capa():
    alvo = {**_com_nos(_maquina("n", "maquina.cpu", "maquina.memoria")), "nao_coletado": [OBSOLETO]}
    assert USO_POR_NO not in br._pendencias_novo([alvo]) and br._faltou([alvo]) == []


def test_o_texto_do_coletor_e_o_que_o_filtro_procura():
    assert USO_POR_NO == "uso de CPU/mem em tempo real por nó"


def test_regra_sem_sublinhado_nem_catalogo_nao_derruba_a_capa():
    assert "Spof" in _capa([_achado("spof", "high")])
