# tests/test_configurar_escrita.py
import configurar


def test_migrar_escreve_o_primeiro_alvos_toml_a_partir_dos_contexts(tmp_path, monkeypatch):
    monkeypatch.setattr(configurar, "LEGADO_NO_HOME", tmp_path / "sem-legado.toml")
    monkeypatch.setattr(configurar, "contexts_docker",
                        lambda: [{"nome": "prod", "endpoint": "tcp://198.51.100.10:2376"},
                                 {"nome": "local", "endpoint": "unix:///var/run/docker.sock"}])
    destino = tmp_path / "alvos.toml"

    codigo = configurar.main(["migrar", "--infra", str(destino)])
    texto = destino.read_text(encoding="utf-8")

    assert codigo == 0
    assert 'nome = "prod"' in texto and 'tipo = "docker"' in texto
    assert 'context = "prod"' in texto
    assert oct(destino.stat().st_mode)[-3:] == "600"


def test_migrar_nunca_sobrescreve_o_que_ja_existe(tmp_path, capsys):
    destino = tmp_path / "alvos.toml"
    destino.write_text('[[alvo]]\nnome = "meu"\ntipo = "docker"\ncontext = "ctx"\n', encoding="utf-8")

    codigo = configurar.main(["migrar", "--infra", str(destino)])

    assert codigo == 2
    assert destino.read_text(encoding="utf-8").count("[[alvo]]") == 1
    assert "já existe" in capsys.readouterr().err


def test_aceitar_acrescenta_no_arquivo_do_projeto_com_as_datas(tmp_path):
    projeto = tmp_path / ".sw-infra-audit.toml"
    projeto.write_text('alvos = ["cluster"]\n', encoding="utf-8")

    codigo = configurar.main(["aceitar", "--projeto", str(projeto), "--alvo", "cluster",
                              "--regra", "spof", "--motivo", "failover manual assumido",
                              "--desde", "2026-09-19", "--meses", "6"])
    texto = projeto.read_text(encoding="utf-8")

    assert codigo == 0
    assert "[[aceite]]" in texto and "failover manual assumido" in texto
    assert 'revisar_em = "2027-03-19"' in texto
    assert 'alvos = ["cluster"]' in texto, "o que já estava no arquivo continua lá"


def test_aceitar_recusa_motivo_vazio(tmp_path, capsys):
    projeto = tmp_path / ".sw-infra-audit.toml"
    projeto.write_text("alvos = []\n", encoding="utf-8")

    codigo = configurar.main(["aceitar", "--projeto", str(projeto), "--alvo", "x",
                              "--regra", "y", "--motivo", "   "])

    assert codigo == 2
    assert "motivo" in capsys.readouterr().err
    assert "[[aceite]]" not in projeto.read_text(encoding="utf-8")


def test_sugerir_propoe_metricas_url_sem_alcancar_host(tmp_path, monkeypatch):
    """A descoberta só PROPÕE: quem alcança host é o coletor, e só depois de declarado."""
    tentativas = []
    import socket as socket_mod
    monkeypatch.setattr(socket_mod, "create_connection",
                        lambda *a, **k: tentativas.append(a))
    monkeypatch.setattr(configurar, "candidatos_de_metricas",
                        lambda context: [{"url": "http://198.51.100.10:9090/metrics",
                                          "por_que": "prometheus publicado na porta 9090"}])

    codigo = configurar.main(["alvos", "--sugerir", "--context", "prod"])

    assert codigo == 0 and tentativas == []


def test_ignorar_acrescenta_a_pasta_no_gitignore_uma_vez_so(tmp_path):
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

    configurar.main(["ignorar", "--repo", str(tmp_path), "--pasta", "docs/infra"])
    configurar.main(["ignorar", "--repo", str(tmp_path), "--pasta", "docs/infra"])
    texto = (tmp_path / ".gitignore").read_text(encoding="utf-8")

    assert texto.count("docs/infra/*") == 1
    assert texto.count("!docs/infra/config.toml") == 1
    assert "node_modules/" in texto


def test_sugerir_roda_todo_comando_no_context_pedido(monkeypatch):
    """A proposta lê o cluster ESCOLHIDO. Sem passar o context ao runner, ela leria o daemon
    local e ofereceria as métricas da máquina de quem rodou como se fossem as do cluster."""
    import json
    from lib.coletores import docker as docker_mod
    chamadas = []

    def falso_run(cmd, timeout, errors=None, context=None):
        chamadas.append((list(cmd), context))
        if cmd[1:3] == ["context", "inspect"]:
            return json.dumps([{"Endpoints": {"docker": {"Host": "tcp://198.51.100.10:2376"}}}])
        return None

    monkeypatch.setattr(configurar, "run", falso_run)
    monkeypatch.setattr(docker_mod, "run", falso_run)

    candidatos = configurar.candidatos_de_metricas("prod")

    assert isinstance(candidatos, list)                  # não estoura no meio do caminho
    assert chamadas, "nenhum comando docker chegou a rodar"
    assert {context for _, context in chamadas} == {"prod"}


def test_sugerir_sem_host_no_context_nao_quebra_a_impressao(capsys, monkeypatch):
    """Endpoint sem host (socket local) faz a URL vir vazia — imprimir isso não pode estourar."""
    monkeypatch.setattr(configurar, "candidatos_de_metricas",
                        lambda context: [{"url": None, "por_que": "prometheus sem porta publicada"}])

    codigo = configurar.main(["alvos", "--sugerir", "--context", "local"])

    assert codigo == 0
    assert "prometheus sem porta publicada" in capsys.readouterr().out


def test_aceitar_nunca_grava_data_que_nao_existe(tmp_path):
    """31/03 + 6 meses = 30/09. Gravar "2026-09-31" fazia a PRÓXIMA auditoria morrer ao ler
    o aceite — o registro de risco derrubando a auditoria que ele deveria explicar."""
    from datetime import date
    projeto = tmp_path / ".sw-infra-audit.toml"

    codigo = configurar.main(["aceitar", "--projeto", str(projeto), "--alvo", "cluster",
                              "--regra", "spof", "--motivo", "banco legado",
                              "--desde", "2026-03-31", "--meses", "6"])
    texto = projeto.read_text(encoding="utf-8")

    assert codigo == 0
    assert 'revisar_em = "2026-09-30"' in texto
    for linha in texto.splitlines():                      # toda data do bloco é uma data de verdade
        if linha.startswith(("desde", "revisar_em")):
            date.fromisoformat(linha.split('"')[1])


def test_aceitar_recusa_desde_que_nao_e_data(tmp_path, capsys):
    projeto = tmp_path / ".sw-infra-audit.toml"

    codigo = configurar.main(["aceitar", "--projeto", str(projeto), "--alvo", "cluster",
                              "--regra", "spof", "--motivo", "x", "--desde", "31/03/2026"])

    assert codigo == 2
    assert "AAAA-MM-DD" in capsys.readouterr().err
    assert not projeto.exists(), "arquivo do projeto não pode ser tocado quando a entrada é inválida"


def test_migrar_escreve_na_pasta_do_relatorio_e_garante_o_gitignore(tmp_path, monkeypatch):
    """O alvos.toml nasce dentro do projeto — e a pasta entra no .gitignore no mesmo ato,
    senão o arquivo de conexão nasce versionado."""
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n', encoding="utf-8")
    monkeypatch.setattr(configurar, "LEGADO_NO_HOME", tmp_path / "sem-legado.toml")
    monkeypatch.setattr(configurar, "contexts_docker",
                        lambda: [{"nome": "prod", "endpoint": "tcp://198.51.100.10:2376"}])

    codigo = configurar.main(["migrar", "--padrao", str(tmp_path / "default.toml")])
    destino = tmp_path / "docs" / "infra" / "alvos.toml"

    assert codigo == 0
    assert 'context = "prod"' in destino.read_text(encoding="utf-8")
    assert oct(destino.stat().st_mode)[-3:] == "600"
    assert "docs/infra/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")


def test_migrar_traz_o_alvos_toml_antigo_do_home(tmp_path, monkeypatch):
    """Quem já tinha alvos no ~/.config não recomeça do zero: o conteúdo vem junto."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n', encoding="utf-8")
    legado = tmp_path / "home" / ".config" / "sw-infra-audit" / "alvos.toml"
    legado.parent.mkdir(parents=True)
    legado.write_text('[[alvo]]\nnome = "cluster"\ntipo = "docker"\ncontext = "prod"\n',
                      encoding="utf-8")
    monkeypatch.setattr(configurar, "LEGADO_NO_HOME", legado)
    monkeypatch.setattr(configurar, "contexts_docker", lambda: [])

    codigo = configurar.main(["migrar", "--padrao", str(tmp_path / "default.toml")])
    texto = (tmp_path / "docs" / "infra" / "alvos.toml").read_text(encoding="utf-8")

    assert codigo == 0
    assert 'nome = "cluster"' in texto and 'context = "prod"' in texto


def _git_ignora(pasta, caminho):
    import subprocess
    return subprocess.run(["git", "check-ignore", "-q", "--", caminho],
                          cwd=pasta).returncode == 0


def test_ignorar_esconde_a_pasta_mas_deixa_o_config_visivel(tmp_path, monkeypatch):
    """A prova é o próprio git: relatório e alvos ignorados, config.toml versionado."""
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)

    codigo = configurar.main(["ignorar", "--repo", str(tmp_path), "--pasta", "docs/infra"])

    assert codigo == 0
    assert _git_ignora(tmp_path, "docs/infra/alvos.toml")
    assert _git_ignora(tmp_path, "docs/infra/2026-09-19_1000/report.json")
    assert not _git_ignora(tmp_path, "docs/infra/config.toml")


def test_ignorar_substitui_a_forma_antiga_que_engole_a_pasta_inteira(tmp_path, monkeypatch):
    """`docs/infra/` ignora o diretório: o git nem entra nele, e a negação não salva o
    config.toml. A linha antiga precisa sair, não conviver."""
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("node_modules/\ndocs/infra/\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    configurar.main(["ignorar", "--repo", str(tmp_path), "--pasta", "docs/infra"])
    texto = (tmp_path / ".gitignore").read_text(encoding="utf-8")

    assert "docs/infra/\n" not in texto and "docs/infra/*" in texto
    assert "node_modules/" in texto, "o que já estava no .gitignore continua"
    assert not _git_ignora(tmp_path, "docs/infra/config.toml")


def test_ignorar_e_idempotente(tmp_path, monkeypatch):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)

    configurar.main(["ignorar", "--repo", str(tmp_path), "--pasta", "docs/infra"])
    primeiro = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    configurar.main(["ignorar", "--repo", str(tmp_path), "--pasta", "docs/infra"])

    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == primeiro


def test_aceitar_grava_no_config_do_projeto_em_docs_infra(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    codigo = configurar.main(["aceitar", "--alvo", "cluster", "--regra", "spof",
                              "--motivo", "failover manual", "--desde", "2026-09-19"])
    destino = tmp_path / "docs" / "infra" / "config.toml"

    assert codigo == 0
    assert "[[aceite]]" in destino.read_text(encoding="utf-8")


def test_aceitar_por_componente_grava_o_componente(tmp_path):
    """Sem `--componente`, o fluxo documentado gravava um aceite que casava TODAS as filas sem
    consumidor do alvo — de todos os brokers. É o aceite amplo que a identidade composta existe
    para evitar, entrando pela porta da ferramenta."""
    import tomllib

    projeto = tmp_path / "config.toml"

    codigo = configurar.main(["aceitar", "--projeto", str(projeto), "--alvo", "prod",
                              "--componente", "broker", "--regra", "fila_sem_consumidor",
                              "--objeto", "emails@staging",
                              "--motivo", "fila de homologação sem consumidor por desenho",
                              "--desde", "2026-09-21"])
    aceite = tomllib.loads(projeto.read_text(encoding="utf-8"))["aceite"][0]

    assert codigo == 0
    assert aceite["componente"] == "broker"
    assert aceite["objeto"] == "emails@staging"


def test_aceitar_com_aspas_no_motivo_continua_toml_valido(tmp_path):
    """O bloco era montado com f-string sem escapar nada: um motivo com aspas quebrava o
    `config.toml` inteiro, e com ele toda a configuração do projeto."""
    import tomllib

    projeto = tmp_path / "config.toml"

    configurar.main(["aceitar", "--projeto", str(projeto), "--alvo", "prod",
                     "--regra", "SEC_USER_ROOT",
                     "--motivo", 'imagem "legada" do fornecedor \\ sem USER',
                     "--desde", "2026-09-21"])
    aceite = tomllib.loads(projeto.read_text(encoding="utf-8"))["aceite"][0]

    assert aceite["motivo"] == 'imagem "legada" do fornecedor \\ sem USER'


def test_aceitar_nao_deixa_o_motivo_injetar_chave(tmp_path):
    """Uma quebra de linha no motivo não pode virar um `componente = ...` escrito à revelia."""
    import tomllib

    projeto = tmp_path / "config.toml"

    configurar.main(["aceitar", "--projeto", str(projeto), "--alvo", "prod",
                     "--regra", "SEC_USER_ROOT",
                     "--motivo", 'x"\nobjeto = "tudo',
                     "--desde", "2026-09-21"])
    aceite = tomllib.loads(projeto.read_text(encoding="utf-8"))["aceite"][0]

    assert "objeto" not in aceite
