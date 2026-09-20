# tests/test_build_report_v2.py
import json

import build_report


def relatorio():
    return {
        "schema_version": 3, "generated_at": "2026-09-19T10:00:00Z",
        "alvos": [
            {"nome": "cluster", "tipo": "docker", "onde": "context: ctx", "saude": "🟡",
             "dimensoes": {"seguranca": {"nota": "🟡"}}, "fatos": {}, "analise": "Traefik sozinho.",
             "achados": [{"regra": "spof", "objeto": "traefik", "severidade": "high",
                          "detalhe": "1 réplica", "alvo": "cluster"}], "nao_coletado": []},
            {"nome": "site", "tipo": "http", "onde": "https://exemplo.invalido/health",
             "saude": "sem dados", "dimensoes": {}, "fatos": {}, "achados": [], "analise": "",
             "nao_coletado": [{"valor": None, "motivo": "alvo não confirmado nesta execução"}]}],
        "inventario": [{"nome": "cluster", "tipo": "docker", "onde": "context: ctx", "saude": "🟡"},
                       {"nome": "site", "tipo": "http", "onde": "https://exemplo.invalido/health",
                        "saude": "sem dados"}],
        "aceites": [{"alvo": "cluster", "regra": "sem_backup", "motivo": "backup no provedor",
                     "desde": "2026-01-01", "revisar_em": "2027-01-01", "origem": "infra",
                     "vencido": False, "obsoleto": False}],
        "historico": {"vs": "2026-09-18_1500", "resolvidos": ["cluster · sem_tls · api"], "novos": []},
        "resumo": "Um cluster com ponto único.", "fortes": ["TLS em dia"],
        "fracos": ["Traefik sem redundância"],
        "recomendacoes": [{"alvo": "cluster", "titulo": "Subir segunda réplica do Traefik",
                           "porque": "hoje é ponto único de 17 apps",
                           "comando": "docker service update --replicas 2 traefik_traefik",
                           "impacto": "alto", "esforco": "baixo"}]}


def montar(tmp_path, dados=None, monkeypatch=None):
    """Sem Chromium: o PDF tem teste próprio, e rodar o navegador em cada teste só deixa lixo."""
    pasta = tmp_path / "2026-09-19_1000"
    pasta.mkdir(parents=True)
    (pasta / "report.json").write_text(json.dumps(dados or relatorio()), encoding="utf-8")
    original = build_report.find_chromium
    build_report.find_chromium = lambda: None
    try:
        build_report.main(["--dir", str(pasta)])
    finally:
        build_report.find_chromium = original
    return (pasta / "relatorio.html").read_text(encoding="utf-8")


def test_o_que_existe_vem_antes_do_que_esta_errado(tmp_path):
    """A ordem de leitura é a do relatório: primeiro o mapa do que existe, depois o
    diagnóstico. Cobrar isso pelo CONTEÚDO, e não pelo título da seção, sobrevive a
    reorganizar as seções."""
    html = montar(tmp_path)

    assert "context: ctx" in html and "exemplo.invalido" in html
    assert html.index("context: ctx") < html.index('id="achados"'), \
        "o mapa do que existe vem antes do diagnóstico"


def test_nao_existe_nota_unica_da_infraestrutura(tmp_path):
    html = montar(tmp_path)

    assert "Saúde geral" not in html and "Nota geral" not in html
    assert "1 alvo sem dados" in html or "sem dados" in html


def test_alvo_sem_dados_aparece_com_o_motivo(tmp_path):
    html = montar(tmp_path)

    assert "não confirmado nesta execução" in html


def test_aceites_aparecem_com_origem_motivo_e_revisao(tmp_path):
    html = montar(tmp_path)

    assert "Riscos aceitos" in html
    assert "backup no provedor" in html and "infra" in html and "2027-01-01" in html


def test_recomendacao_traz_o_comando_pronto_e_o_alvo(tmp_path):
    html = montar(tmp_path)

    assert "docker service update --replicas 2 traefik_traefik" in html
    assert "cluster" in html


def test_mesmo_json_gera_o_mesmo_html(tmp_path):
    """Restrição 4: com as mesmas entradas, mesmos bytes."""
    um = montar(tmp_path / "a")
    dois = montar(tmp_path / "b")

    assert um == dois


def test_relatorio_v1_e_recusado_com_mensagem(tmp_path, capsys):
    pasta = tmp_path / "antigo"
    pasta.mkdir()
    (pasta / "report.json").write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    codigo = build_report.main(["--dir", str(pasta)])

    assert codigo == 2
    assert "schema" in capsys.readouterr().err


def test_texto_do_agente_nao_injeta_secao_no_relatorio(tmp_path):
    """Substituir marcador em laço reprocessa o que já foi inserido: um %%ALVOS%% escrito no
    resumo duplicaria a seção inteira."""
    dados = relatorio()
    dados["resumo"] = "tudo certo %%ALVOS%% %%HISTORICO%%"

    html = montar(tmp_path, dados)

    assert html.count("<h2>Por alvo</h2>") == 1
    assert "%%ALVOS%%" in html, "o marcador aparece como texto, não como seção"


def test_relatorio_v2_e_recusado_com_mensagem_que_explica(tmp_path):
    """Sem migração silenciosa: o relatório antigo fica onde está, como histórico."""
    import pytest
    v2 = {"schema_version": 2, "generated_at": "2026-09-19T10:00:00Z", "alvos": []}
    with pytest.raises(ValueError) as erro:
        build_report.build(v2, tmp_path)
    assert "v3" in str(erro.value) and "histórico" in str(erro.value)
