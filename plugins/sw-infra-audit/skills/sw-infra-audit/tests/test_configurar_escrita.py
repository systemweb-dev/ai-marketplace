# tests/test_configurar_escrita.py
import configurar


def test_migrar_escreve_o_primeiro_alvos_toml_a_partir_dos_contexts(tmp_path, monkeypatch):
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

    assert texto.count("docs/infra/") == 1
    assert "node_modules/" in texto
