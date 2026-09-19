# tests/test_report_montar.py
import json

import report
from lib import pastas
from test_report_validar import FATOS, achado


def montar(fatos=None, achados=None, data="2026-09-18"):
    corpo = {"versao": 1, "achados": [achado()], "nao_e_problema": []}
    return report.montar(fatos or FATOS, achados or corpo, data)


def test_cabecalho_traz_escopo_stack_e_inventario():
    texto = montar()

    assert texto.startswith("# Saúde dos testes — .\n")
    assert "pytest" in texto and "1 arquivo" in texto and "2 teste" in texto


def test_sem_execucao_cobertura_e_velocidade_ficam_sem_dados():
    texto = montar()

    assert "| Cobertura | ⚪ sem dados |" in texto
    assert "| Velocidade | ⚪ sem dados |" in texto


def test_suite_vermelha_derruba_a_confiabilidade():
    fatos = dict(FATOS, execucao=dict(FATOS["execucao"], rodou=True, verde=False, falhou=3,
                                      duracao_faixa="10-60s"))

    texto = montar(fatos=fatos)

    assert "| Confiabilidade | 🔴" in texto
    assert "3 teste(s) falhando" in texto


def test_achado_de_confianca_alta_vira_secao_propria_com_arquivo_e_linha():
    texto = montar()

    assert "### Confiança alta" in texto
    assert "`tests/unit/test_a.py:3`" in texto
    assert "reativar ou apagar" in texto


def test_confianca_baixa_entra_como_verificar_e_nunca_como_corrigir():
    corpo = {"versao": 1, "achados": [achado(confianca="baixa", sinal=None)], "nao_e_problema": []}

    texto = montar(achados=corpo)

    assert "### Verificar" in texto
    assert "### Confiança baixa" not in texto


def test_o_que_nao_e_problema_aparece_no_fim():
    corpo = {"versao": 1, "achados": [],
             "nao_e_problema": [{"caminho": "tests/unit/test_a.py", "motivo": "convenção do time"}]}

    texto = montar(achados=corpo)

    assert "## O que não é problema" in texto and "convenção do time" in texto


def test_texto_do_agente_vira_uma_linha_so():
    corpo = {"versao": 1, "achados": [achado(problema="linha um\n## título falso\nlinha dois")],
             "nao_e_problema": []}

    texto = montar(achados=corpo)

    assert "linha um ## título falso linha dois" in texto
    assert not any(linha.startswith("#") for linha in texto.splitlines()
                   if "título falso" in linha), "texto do agente não pode virar seção do relatório"


def test_relatorio_e_deterministico():
    """Restrição 4: a ordem em que o agente escreveu os achados não pode mudar o relatório."""
    um = achado(linha=1, caminho="tests/unit/test_a.py", regra="a", confianca="media", sinal=None)
    dois = achado(linha=2, caminho="tests/unit/test_a.py", regra="b", confianca="media", sinal=None)

    direto = montar(achados={"versao": 1, "achados": [um, dois], "nao_e_problema": []})
    invertido = montar(achados={"versao": 1, "achados": [dois, um], "nao_e_problema": []})

    assert direto == invertido
    assert direto.index("regra: a" if "regra: a" in direto else "*(a,") < \
        direto.index("*(b,"), "a ordem impressa é por arquivo e linha, não pela ordem de escrita"


def test_gravar_cria_o_arquivo_e_registra_no_exclude(repo):
    destino, avisos = report.gravar(repo.path, "# Saúde dos testes — .\n")
    exclude = (repo.path / ".git" / "info" / "exclude").read_text(encoding="utf-8")

    assert destino == repo.path / "test-health-report.md"
    assert destino.read_text(encoding="utf-8").startswith("# Saúde dos testes")
    assert exclude.count("/test-health-report.md") == 1
    assert avisos == []


def test_gravar_duas_vezes_nao_duplica_a_linha_do_exclude(repo):
    report.gravar(repo.path, "a\n")
    report.gravar(repo.path, "b\n")
    exclude = (repo.path / ".git" / "info" / "exclude").read_text(encoding="utf-8")

    assert exclude.count("/test-health-report.md") == 1


def test_relatorio_versionado_grava_e_avisa(repo):
    (repo.path / "test-health-report.md").write_text("antigo\n", encoding="utf-8")
    repo.git("add", "-A"); repo.git("commit", "-qm", "chore: relatorio")

    _, avisos = report.gravar(repo.path, "novo\n")

    assert any("versionado" in a for a in avisos)


def test_main_recusa_achados_invalidos_com_exit_3(repo, capsys, monkeypatch):
    pastas.criar(repo.path)
    pastas.fatos(repo.path).write_text(json.dumps(dict(FATOS, repo=dict(FATOS["repo"],
        toplevel=str(repo.path), branch="master"))), encoding="utf-8")
    pastas.achados(repo.path).write_text(json.dumps({"versao": 1, "achados": [achado(dimensao="x")],
                                                     "nao_e_problema": []}), encoding="utf-8")

    codigo = report.main(["--repo", str(repo.path), "--data", "2026-09-18"])

    assert codigo == 3
    assert "dimensao" in capsys.readouterr().err
    assert not (repo.path / "test-health-report.md").exists()


def test_main_recusa_fatos_de_outra_branch_com_exit_2(repo, capsys):
    pastas.criar(repo.path)
    pastas.fatos(repo.path).write_text(json.dumps(dict(FATOS, repo=dict(FATOS["repo"],
        toplevel=str(repo.path), branch="outra"))), encoding="utf-8")
    pastas.achados(repo.path).write_text(json.dumps({"versao": 1, "achados": [], "nao_e_problema": []}),
                                         encoding="utf-8")

    codigo = report.main(["--repo", str(repo.path)])

    assert codigo == 2
    assert "outra" in capsys.readouterr().err


def test_regra_do_agente_nao_cria_secao_nem_tabela():
    corpo = {"versao": 1, "achados": [achado(regra="x\n\n## Seção falsa\n\n| a | b |")],
             "nao_e_problema": []}

    texto = montar(achados=corpo)

    assert not any(linha.startswith(("#", "|")) for linha in texto.splitlines()
                   if "Seção falsa" in linha)


def test_cobertura_baixa_nao_sai_verde():
    fatos = dict(FATOS,
                 execucao=dict(FATOS["execucao"], rodou=True, verde=True, duracao_faixa="1-10s"),
                 cobertura={"disponivel": True, "ferramenta": "pytest",
                            "por_arquivo": [{"caminho": "src/a.py", "linhas_pct": 3, "ramos_pct": 0}]})

    texto = montar(fatos=fatos)

    assert "| Cobertura | 🔴" in texto and "3%" in texto


def test_timeout_nao_vira_sem_dados_por_falta_de_autorizacao():
    fatos = dict(FATOS, execucao=dict(FATOS["execucao"], rodou=True, timeout=True, verde=None))

    texto = montar(fatos=fatos)

    assert "a execução não foi autorizada" not in texto
    assert "| Velocidade | 🔴" in texto


def test_teste_lento_tira_a_velocidade_do_verde():
    fatos = dict(FATOS, execucao=dict(FATOS["execucao"], rodou=True, verde=True,
                                      duracao_faixa="1-10s",
                                      lentos=[{"teste": "test_x", "faixa": "1-10s"}]))

    texto = montar(fatos=fatos)

    assert "| Velocidade | 🟡" in texto


def test_relatorio_recusa_escrever_atraves_de_link_simbolico(repo, tmp_path):
    fora = tmp_path / "fora.txt"
    fora.write_text("não pode ser sobrescrito\n", encoding="utf-8")
    (repo.path / "test-health-report.md").symlink_to(fora)
    pastas.criar(repo.path)
    pastas.fatos(repo.path).write_text(json.dumps(dict(FATOS, repo=dict(FATOS["repo"],
        toplevel=str(repo.path), branch="master"))), encoding="utf-8")
    pastas.achados(repo.path).write_text(json.dumps({"versao": 1, "achados": [], "nao_e_problema": []}),
                                         encoding="utf-8")

    codigo = report.main(["--repo", str(repo.path), "--data", "2026-09-18"])

    assert codigo == 2
    assert fora.read_text(encoding="utf-8") == "não pode ser sobrescrito\n"


def test_fatos_sem_as_chaves_esperadas_sai_com_dois(repo, capsys):
    pastas.criar(repo.path)
    pastas.fatos(repo.path).write_text(json.dumps({"versao": 1, "sinais": []}), encoding="utf-8")
    pastas.achados(repo.path).write_text(json.dumps({"versao": 1, "achados": [], "nao_e_problema": []}),
                                         encoding="utf-8")

    assert report.main(["--repo", str(repo.path)]) == 2
    assert "ilegível" in capsys.readouterr().err


def test_em_monorepo_o_relatorio_vai_para_a_raiz_do_pacote(repo):
    (repo.path / "packages/api/tests/unit").mkdir(parents=True)
    (repo.path / "packages/api/tests/unit/test_a.py").write_text("def test_a():\n    assert 1\n",
                                                                 encoding="utf-8")
    fatos = dict(FATOS, repo=dict(FATOS["repo"], toplevel=str(repo.path), branch="master"),
                 escopo={"tipo": "pacote", "raiz": "packages/api"})
    pastas.criar(repo.path)
    pastas.fatos(repo.path).write_text(json.dumps(fatos), encoding="utf-8")
    pastas.achados(repo.path).write_text(json.dumps({"versao": 1,
        "achados": [achado(linha=1, confianca="media", sinal=None)], "nao_e_problema": []}),
        encoding="utf-8")

    assert report.main(["--repo", str(repo.path), "--data", "2026-09-18"]) == 0
    assert (repo.path / "packages/api/test-health-report.md").exists()
    assert not (repo.path / "test-health-report.md").exists()
