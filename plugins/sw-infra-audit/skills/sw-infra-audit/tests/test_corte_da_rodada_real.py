"""Os cortes que a primeira rodada real pediu: filas, nós, recomendações repetidas."""
import re

import build_report as br
from lib import blocos as b
from lib import orcamento_paginas as op
from tests.fixtures.relatorio_grande import relatorio_grande


def _fila(nome, prontas=0, consumidores=1, entrada=None, saida=None, **extra):
    return {"nome": nome, "prontas": prontas, "consumidores": consumidores, "entrada": entrada, "saida": saida, **extra}


def _ordem(html):
    return re.findall(r'<b>(f-[^<]+)</b>', html)


# --- 1. filas
def test_parada_e_lenta_vem_antes_do_maior_volume():
    filas = [_fila("f-grande", 9000, 2, 60, 60), _fila("f-lenta", 5, 2, 90, 10), _fila("f-parada", 3, 0)]
    html = b.render_bloco("fila", {"filas": filas, "filas_max": 8})
    assert _ordem(html) == ["f-parada", "f-lenta", "f-grande"]


def test_ate_oito_linhas_e_as_demais_viram_contagem_por_estado():
    ociosas = [_fila(f"f-ociosa-{i:02d}") for i in range(143)]
    fluindo = [_fila(f"f-flui-{i:02d}", 10 + i, 1, 5, 5) for i in range(29)]
    html = b.render_bloco("fila", {"filas": ociosas + fluindo, "filas_max": 8})
    assert len(_ordem(html)) == 8
    assert "f-flui-28" in html and "f-flui-20" not in html
    assert "Outras 164: 21 fluindo, 143 ociosas." in html


def test_empate_de_volume_sai_sempre_na_mesma_ordem():
    filas = [_fila(f"f-{n}") for n in "cab"]
    assert b.render_bloco("fila", {"filas": filas, "filas_max": 2}) \
        == b.render_bloco("fila", {"filas": filas[::-1], "filas_max": 2})


def test_ate_oito_filas_nao_ha_linha_de_contagem_nem_aviso():
    html = b.render_bloco("fila", {"filas": [_fila(f"f-{i}") for i in range(8)], "filas_max": 8})
    assert "bl-qresto" not in html and op.cortes({"filas": 8})["avisos"] == []


def test_o_corte_de_filas_vale_em_relatorio_pequeno_e_avisa():
    r = op.cortes({"filas": 9})
    assert r["filas_max"] == 8 and any("8 de 9" in a and "report.json" in a for a in r["avisos"])


def test_fixture_mostra_oito_filas_com_o_aviso():
    html = br.render_html_v3(relatorio_grande())
    assert html.count('class="bl-q bl-q-') == 8
    assert "As filas mostram 8 de 150" in html and "pedidos-149" not in html


# --- 2. nós e capacidade
def test_por_aplicacao_e_nos_e_capacidade_saem_do_relatorio():
    html = br.render_html_v3(relatorio_grande())
    assert "Por aplicação" not in html and "Nós e capacidade" not in html
    assert "exemplo.test" not in html, "as rotas ficam só no report.json"


def _bloco_de_maquinas(html):
    return html.split("<h3>Máquinas</h3>", 1)[1].split("</section>", 1)[0]


def test_resumo_dos_nos_fica_no_bloco_de_maquinas_mesmo_sem_medida():
    bloco = _bloco_de_maquinas(br.render_html_v3(relatorio_grande()))
    assert "Não medido" in bloco and bloco.count("<tr>") == 5
    assert "no-3" in bloco and "4 vCPU · 16.0 GB" in bloco and "exit 137 (SIGKILL)" in bloco and "×" not in bloco


def test_no_que_nao_esta_pronto_aparece_em_vermelho():
    html = b.render_bloco("maquinas", {"nos": [{"nome": "n", "estado": "Down"}]})
    assert '<b class="bl-c-crit">Down</b>' in html


def test_disco_e_tls_viram_uma_linha_cada_sem_tabela():
    bloco = _bloco_de_maquinas(br.render_html_v3(relatorio_grande()))
    assert bloco.count("Disco do nó conectado em aurora") == 1
    assert "TLS do acesso a aurora: 2 certificados, o primeiro (cert.pem) vence em 200 dias." in bloco
    assert bloco.count("<table") == 1 and "ca.pem" not in bloco


def test_motivo_de_disco_e_tls_nao_coletados_continua_visivel():
    assert "não coletado, sem acesso" in br._linha_de_disco("a", {"status": "n/a", "reason": "sem acesso"})
    assert "sem TLS" in br._linha_de_tls("a", {"status": "n/a", "reason": "sem TLS"})
    assert "(b.pem) venceu há 3 dias" in br._linha_de_tls(
        "a", {"certs": [{"file": "a.pem", "days_left": 9}, {"file": "b.pem", "days_left": -3}]})


# --- o que o spec protege
def test_componente_sem_papel_provado_nunca_e_cortado():
    alvo = {"nome": "a", "cobertura": {"pct": 50, "mudos": [
        {"componente": f"comp-{i:02d}", "pergunta": "<identidade>", "motivo": "m"} for i in range(30)]}}
    html = br._pendencias_novo([alvo])
    assert all(f"comp-{i:02d}" in html for i in range(30))


# --- 3. recomendações
def _rec(titulo, comando=None, **extra):
    return {"titulo": titulo, "porque": f"motivo de {titulo}", "comando": comando, **extra}


def _recs(n):
    return [_rec(f"rec-{i}", f"cmd --opcao {i}", esforco="baixo") for i in range(n)]


def test_recomendacao_da_capa_fica_so_com_o_comando():
    html = br._outras_recomendacoes(_recs(1), set())
    assert "cmd --opcao 0" in html and "Prioridade 1 · esforço baixo" in html
    assert "rec-0" not in html


def test_comando_que_ja_esta_no_problema_agrupado_some_da_lista():
    assert br._outras_recomendacoes(_recs(1), set(), "<pre>cmd   --opcao\n0</pre>") == ""
    assert br._outras_recomendacoes(_recs(1), set(), "<p>use <code>cmd --opcao 0</code></p>") == ""


def test_comando_parecido_nao_conta_como_repetido():
    assert "cmd --opcao 0" in br._outras_recomendacoes(_recs(1), set(), "<pre>cmd --opcao 0 --forca</pre>")


def test_comando_com_caracter_escapado_no_problema_conta_como_repetido():
    recs = [_rec("r", "a && b")]
    assert br._outras_recomendacoes(recs, set(), "<pre>a &amp;&amp; b</pre>") == ""


def test_fora_da_capa_a_recomendacao_continua_inteira_e_mesmo_com_comando_repetido():
    html = br._outras_recomendacoes(_recs(6), set(), "<pre>cmd --opcao 5</pre>")
    assert "rec-5" in html and "motivo de rec-5" in html and '<span class="o n">6</span>' in html


def test_nenhuma_recomendacao_desaparece_do_documento():
    r = relatorio_grande()
    html = br.render_html_v3(r)
    for rec in r["recomendacoes"]:
        assert rec["titulo"] in html, rec["titulo"]
        assert rec["comando"] in html, rec["comando"]


def test_titulo_da_capa_aparece_uma_vez_so():
    r = relatorio_grande()
    html = br.render_html_v3(r)
    assert all(html.count(rec["titulo"]) == 1 for rec in r["recomendacoes"])
    assert html.count("Prioridade 1 ·") == 1


def test_comando_escapado_na_linha_curta():
    assert "<script>" not in br._outras_recomendacoes([_rec("r", "echo '<script>'", esforco="<u>")], set())
    assert "<u>" not in br._outras_recomendacoes([_rec("r", "x", esforco="<u>")], set())
