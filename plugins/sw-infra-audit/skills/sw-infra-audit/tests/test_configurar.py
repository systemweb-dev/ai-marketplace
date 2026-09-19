# tests/test_configurar.py
import configurar


def preparar(tmp_path, projeto_texto='alvos = ["cluster"]\n[relatorio]\npasta = "docs/auditoria"\n'):
    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n'
                                           '[limites]\ntimeout_por_comando = 20\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text('[[alvo]]\nnome = "cluster"\ntipo = "docker"\n'
                                         'context = "ctx"\n', encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text(projeto_texto, encoding="utf-8")
    return ["--padrao", str(tmp_path / "default.toml"),
            "--infra", str(tmp_path / "alvos.toml"),
            "--projeto", str(tmp_path / ".sw-infra-audit.toml")]


def test_explicar_mostra_valor_e_origem_de_cada_chave(tmp_path, capsys):
    codigo = configurar.main(["config", "--explicar", *preparar(tmp_path)])
    saida = capsys.readouterr().out

    assert codigo == 0
    assert "relatorio.pasta" in saida and "docs/auditoria" in saida and "projeto" in saida
    assert "limites.timeout_por_comando" in saida and "default" in saida


def test_explicar_lista_os_alvos_e_de_onde_vieram(tmp_path, capsys):
    configurar.main(["config", "--explicar", *preparar(tmp_path)])
    saida = capsys.readouterr().out

    assert "cluster" in saida and "docker" in saida


def test_chave_de_conexao_no_projeto_sai_com_dois_e_explica(tmp_path, capsys):
    args = preparar(tmp_path, projeto_texto='[[alvo]]\nnome = "x"\nhost = "exemplo.invalido"\n')

    codigo = configurar.main(["config", "--explicar", *args])

    assert codigo == 2
    assert "host" in capsys.readouterr().err


def test_saida_e_estavel_entre_execucoes(tmp_path, capsys):
    args = preparar(tmp_path)
    configurar.main(["config", "--explicar", *args])
    primeira = capsys.readouterr().out
    configurar.main(["config", "--explicar", *args])

    assert capsys.readouterr().out == primeira


def test_explicar_nao_imprime_valor_que_parece_segredo(tmp_path, capsys):
    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "c"\ntipo = "docker"\ncontext = "ctx"\n\n'
        '[pg]\npassword = "nao-pode-vazar"\ntoken = "nem-isso"\n', encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = ["c"]\n', encoding="utf-8")

    configurar.main(["config", "--explicar",
                     "--padrao", str(tmp_path / "default.toml"),
                     "--infra", str(tmp_path / "alvos.toml"),
                     "--projeto", str(tmp_path / ".sw-infra-audit.toml")])
    saida = capsys.readouterr().out

    assert "nao-pode-vazar" not in saida and "nem-isso" not in saida
    assert "pg.password" in saida and "***" in saida
