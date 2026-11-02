"""Ajustes pedidos pelo dono depois de ler o PDF de uma rodada real."""
import json
import re
import shutil
import subprocess

import pytest

import build_report as br
from lib.blocos import render_bloco
from lib.dados_blocos import dados_do_papel
from lib.redact import scrub_text
from tests.test_build_report_v3 import relatorio

com_pdf = pytest.mark.skipif(not br.find_chromium() or not shutil.which("pdftotext"),
                             reason="Chromium ou pdftotext ausente: PDF não verificado")
FALSO = "ValorFalso9x"  # noscan


# --- 1. redação de texto livre
@pytest.mark.parametrize("modelo", [
    "mysqldump --password={v} app",
    "mysqldump --password {v} app",
    'cli --password "{v} com espaco" app',
    "cli login --token {v}",
    "cli login --token={v}",
    "cli --secret {v}",
    "cli --secret={v}",
    "PASSWORD={v} ./roda.sh",
    "export PGPASSWORD={v}",
    "MYSQL_ROOT_PASSWORD={v} docker compose up",
    "DEPLOY_TOKEN={v} ./roda.sh",
    "APP_SECRET={v} ./roda.sh",
    "API_KEY={v} ./roda.sh",
    "`PGPASSWORD={v}`",
    "curl -H 'Authorization: Bearer {v}' https://exemplo.invalido",
    'curl -H "Authorization: Basic {v}" https://exemplo.invalido',
    "mysql -uroot -p{v} app",
    "docker exec db mysqldump -h db -p{v} app | gzip",
    "mysql -p'{v} com espaco' app",
    "https://admin:{v}@exemplo.invalido/api",
    "https://admin:{v}@resto@exemplo.invalido/api",
    "https://admin:{v}/resto@exemplo.invalido/api",
])
def test_valor_de_segredo_nao_passa(modelo):
    saida = scrub_text(modelo.format(v=FALSO), limit=None)
    assert FALSO not in saida and "resto" not in saida and "com espaco" not in saida
    assert "***" in saida


@pytest.mark.parametrize("texto", [
    "mysqldump --password=$SENHA app",
    "mysqldump --password=${SENHA} app",
    "mysqldump --password $SENHA app",
    'mysqldump --password "$SENHA" app',
    "PGPASSWORD=$SENHA psql",
    "PGPASSWORD=${SENHA} psql",
    "DEPLOY_TOKEN=${SENHA} ./roda.sh",
    'curl -H "Authorization: Bearer $TOKEN" https://exemplo.invalido',
    "mysql -uroot -p$SENHA app",
    'mysql -uroot -p"$SENHA" app',
    "mysql -uroot -p app",
    "mysql -P 3306 app",
    "docker run -p3306:3306 mysql:8",
    "docker login --password-stdin",
    "docker service update --secret-add credencial app",
    "use a opção --password",
    "cli --token --verbose",
    "a flag --password para definir",
    "defina PGPASSWORD no ambiente",
    "a variável DEPLOY_TOKEN não existe",
    "a chave API_KEY está vazia",
    "o cabeçalho Authorization: Bearer",
    "https://exemplo.invalido:8080/caminho?contato=fulano@exemplo.invalido",
    "https://exemplo.invalido:8080/@perfil",
    "fulano@exemplo.invalido",
])
def test_referencia_e_nome_sem_valor_ficam_intactos(texto):
    assert scrub_text(texto, limit=None) == texto


def test_redigir_duas_vezes_da_o_mesmo_texto():
    uma = scrub_text(f"PASSWORD={FALSO} https://a:{FALSO}@exemplo.invalido", limit=None)
    assert scrub_text(uma, limit=None) == uma


def test_o_limite_de_tamanho_continua():
    assert len(scrub_text("x" * 500)) == 200


def _relatorio_com_valores_falsos():
    r = relatorio()
    r["resumo"] = f"Rode com PGPASSWORD={FALSO} para conferir."
    r["recomendacoes"] = [{"titulo": f"Trocar --token {FALSO}", "porque": f"API_KEY={FALSO} ficou no texto.",
                           "comando": f"mysql -uroot -p{FALSO} app --password=$SENHA",
                           "impacto": "alto", "esforco": "baixo"}]
    r["alvos"][0]["analise"] = f"Authorization: Bearer {FALSO}"
    return r


def test_valores_falsos_nao_chegam_ao_html():
    html = br.render_html_v3(_relatorio_com_valores_falsos())
    assert FALSO not in html and "PGPASSWORD=***" in html and "--password=$SENHA" in html


@com_pdf
def test_valores_falsos_nao_chegam_ao_pdf(tmp_path):
    pdf = br.build(_relatorio_com_valores_falsos(), str(tmp_path), formato="html+pdf")["pdf"]
    texto = subprocess.run(["pdftotext", pdf, "-"], check=True, capture_output=True, text=True).stdout
    assert FALSO not in texto and "PGPASSWORD=***" in texto


# --- 2. trava do resumo
FRASE = "O cluster está no ar."


def _rodar(tmp_path, resumo, capsys):
    r = relatorio()
    r["resumo"] = resumo
    (tmp_path / "report.json").write_text(json.dumps(r), encoding="utf-8")
    codigo = br.main(["--dir", str(tmp_path), "--formato", "html"])
    return codigo, capsys.readouterr().err


@pytest.mark.parametrize("resumo", [
    f"{FRASE} {FRASE} {FRASE}",
    "Primeira? Segunda! Terceira.",
    "x" * 281,
    "- primeira\n- segunda\n- terceira",
    "Primeira.\n\nSegunda.\n\nTerceira.",
])
def test_resumo_grande_para_o_build_sem_gerar_relatorio(tmp_path, capsys, resumo):
    codigo, erro = _rodar(tmp_path, resumo, capsys)
    assert codigo == 2 and "resumo" in erro and "reescreva" in erro.lower()
    assert not (tmp_path / "relatorio.html").exists()


def test_a_mensagem_nao_repete_o_texto_do_agente(tmp_path, capsys):
    _, erro = _rodar(tmp_path, f"{FRASE} PASSWORD={FALSO}. {FRASE} {FRASE}", capsys)
    assert FALSO not in erro


@pytest.mark.parametrize("resumo", [
    "",
    FRASE,
    f"{FRASE} {FRASE}",
    "x" * 280,
    "A CPU fica em 4,5 % e a versão 1.2.3 de 23/10 subiu, de 3.650 para 504, em exemplo.invalido.",
    "Havia filas, p.ex. a de e-mail, sem consumidor etc. e isso segue igual.",
])
def test_resumo_dentro_do_limite_passa(tmp_path, capsys, resumo):
    codigo, _ = _rodar(tmp_path, resumo, capsys)
    assert codigo == 0 and (tmp_path / "relatorio.html").exists()


@pytest.mark.parametrize("entrada, esperado", [
    ("Continua 🔴 pelas filas.", "Continua degradado pelas filas."),
    ("Foi de 🟡 para 🟢.", "Foi de atenção para operacional."),
    ("🔴 Duas filas paradas.", "Duas filas paradas."),
    ("Segue 🔴 degradado.", "Segue degradado."),
    ("Primeira. 🟢 Segunda.", "Primeira. Segunda."),
    ("Sem emoji.", "Sem emoji."),
])
def test_emoji_de_status_some_do_resumo_sem_mudar_o_sentido(entrada, esperado):
    r = relatorio()
    r["resumo"] = entrada
    capa = br.render_html_v3(r).split('id="bl-capa"', 1)[1].split("</header>", 1)[0]
    assert esperado in capa and not re.search("[🔴🟡🟢]", capa)


# --- 3. serviços web duplicados
def _entrada(nome, fonte, volume=71414):
    return {"nome": nome, "papel": "entrada", "respostas": [
        {"pergunta": "entrada.volume_na_janela", "valor": volume, "fonte": fonte},
        {"pergunta": "entrada.latencia", "valor": 728.15, "fonte": fonte}]}


def _bloco(*componentes):
    return render_bloco("entrada", dados_do_papel("entrada", [{"nome": "c", "componentes": list(componentes)}]))


def test_mesma_medida_da_fonte_inteira_vira_uma_linha_de_proxy():
    html = _bloco(_entrada("loja_nginx", "promql:traefik (exporter inteiro)"),
                  _entrada("borda_traefik", "promql:traefik"))
    assert html.count('class="bl-site"') == 1 and "Proxy (total)" in html
    assert html.count("71,4 mil") == 1 and "loja_nginx" in html and "borda_traefik" in html


def test_resposta_de_urls_em_um_so_proxy_nao_impede_a_fusao():
    com_urls = _entrada("loja_nginx", "promql:traefik (exporter inteiro)")
    com_urls["respostas"].append({"pergunta": "entrada.urls_mais_acessadas", "valor": [], "fonte": "logql:traefik"})
    html = _bloco(com_urls, _entrada("borda_traefik", "promql:traefik"))
    assert html.count('class="bl-site"') == 1 and "Proxy (total)" in html


def test_a_ordem_dos_componentes_nao_muda_o_resultado():
    html = _bloco(_entrada("borda_traefik", "promql:traefik"),
                  _entrada("loja_nginx", "promql:traefik (exporter inteiro)"))
    assert html.count('class="bl-site"') == 1 and "Proxy (total)" in html


def test_numero_diferente_nao_se_funde():
    html = _bloco(_entrada("loja_nginx", "promql:traefik (exporter inteiro)", 10),
                  _entrada("borda_traefik", "promql:traefik", 20))
    assert html.count('class="bl-site"') == 2 and "Proxy (total)" not in html


def test_fonte_diferente_nao_se_funde():
    html = _bloco(_entrada("loja_nginx", "promql:traefik (exporter inteiro)"),
                  _entrada("borda_traefik", "promql:outro"))
    assert html.count('class="bl-site"') == 2


def test_medida_propria_de_cada_um_nao_se_funde_mesmo_igual():
    html = _bloco(_entrada("a", "promql:traefik"), _entrada("b", "promql:traefik"))
    assert html.count('class="bl-site"') == 2 and "Proxy (total)" not in html


# --- 4. filas
def _fila(**campos):
    return render_bloco("fila", {"filas": [{"nome": "fila-a", "prontas": 10, "consumidores": 0, **campos}]})


@pytest.mark.parametrize("taxas", [{}, {"entrada": 5}, {"saida": 5}])
def test_parada_sem_ritmo_diz_uma_vez_e_sem_colunas_vazias(taxas):
    html = _fila(**taxas)
    assert html.count("Ritmo não medido") == 1 and "sem dado" not in html
    assert "Entra" not in html and "Sai<" not in html and "/min" not in html


def test_parada_com_as_duas_taxas_mostra_o_saldo():
    html = _fila(entrada=9, saida=3)
    assert "+6/min" in html and "Entra" in html and "Sai<" in html and "Ritmo não medido" not in html


def test_parada_com_taxas_zeradas_tem_ritmo_medido():
    html = _fila(entrada=0, saida=0)
    assert "0/min" in html and "Ritmo não medido" not in html


def test_fila_sem_uma_das_taxas_nao_mostra_saldo():
    html = _fila(consumidores=2, entrada=9)
    assert html.count("Ritmo não medido") == 1 and "9/min" in html and '<div class="bl-qs"><b' not in html


# --- 5. páginas
def _texto_das_paginas(pdf):
    texto = subprocess.run(["pdftotext", pdf, "-"], check=True, capture_output=True, text=True).stdout
    return texto.split("\f")[:-1]


def _preenchimento(pdf):
    """Até onde vai o texto de cada página, de 0 a 1."""
    xml = subprocess.run(["pdftotext", "-bbox", pdf, "-"], check=True, capture_output=True, text=True).stdout
    return [max(map(float, re.findall(r'yMax="([\d.]+)"', corpo)), default=0) / float(altura)
            for altura, corpo in re.findall(r'<page width="[\d.]+" height="([\d.]+)">(.*?)</page>', xml, re.S)]


def _grande():
    from tests.fixtures.relatorio_grande import relatorio_grande
    r = relatorio_grande()
    r["alvos"][0]["tendencias"] = {nome: [1, 2, 3] for nome in ("erros", "resposta", "cpu", "memoria", "disco")}
    r["recomendacoes"] = [dict(x, titulo="Título de prioridade do tamanho das mais longas de uma rodada",
                               porque="Motivo escrito pelo agente, do tamanho dos mais longos vistos: duas "
                                      "frases curtas dizendo o que está acontecendo e por que isso importa.")
                          for x in r["recomendacoes"]]
    return r


@com_pdf
def test_capa_cheia_cabe_na_primeira_folha(tmp_path):
    pdf = br.build(_grande(), str(tmp_path), formato="html+pdf")["pdf"]
    assert "Não medido" in " ".join(_texto_das_paginas(pdf)[0].split())


@com_pdf
def test_nenhuma_pagina_intermediaria_fica_quase_vazia(tmp_path):
    pdf = br.build(_grande(), str(tmp_path), formato="html+pdf")["pdf"]
    paginas = _preenchimento(pdf)[:-1]
    assert min(paginas) >= 0.15, [round(p, 2) for p in paginas]


def test_bloco_longo_quebra_entre_linhas_e_nunca_dentro_de_uma():
    css = re.sub(r"/\*.*?\*/", "", open(br.TEMPLATE_V3, encoding="utf-8").read(), flags=re.S)
    regras = {}
    for seletores, corpo in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        for seletor in seletores.split(","):
            regras[seletor.strip()] = regras.get(seletor.strip(), "") + corpo
    for seletor in ("table", ".rec", ".item", ".card", ".app"):
        assert "break-inside:avoid" not in regras.get(seletor, ""), seletor
    for seletor in ("tr", ".bl-q", ".bl-site"):
        assert "break-inside:avoid" in regras.get(seletor, ""), seletor
