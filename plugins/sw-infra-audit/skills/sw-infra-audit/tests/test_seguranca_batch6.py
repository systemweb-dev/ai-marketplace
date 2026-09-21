# tests/test_seguranca_batch6.py
"""O que a revisão do último batch mostrou sobre as garantias escritas na documentação.

Afirmação falsa em documentação de segurança é pior que ausência: quem lê confia. Cada teste
aqui prova uma frase da SKILL.md ou do commands-allowlist.md que, até esta rodada, não era
verdade no código — ou só era verdade porque um teste olhava estreito demais.
"""
import base64
import json
import re
from pathlib import Path

import pytest

import collect
from lib import alvos, http_get
from lib.catalogo_api import CatalogoInvalido, carregar_arquivo

SCRIPTS = Path(collect.__file__).resolve().parent


# --- 1. a recusa de URL com senha imprimia a senha ---

@pytest.mark.parametrize("url", ["amqp://auditoria:SENHA-REAL-123@rabbit:5672",
                                 "http://auditoria:SENHA-REAL-123@rabbit:15672",
                                 "ftp://auditoria:SENHA-REAL-123@rabbit"])
def test_nenhuma_recusa_de_url_repete_a_senha(tmp_path, url):
    """Colar a string de conexão AMQP no lugar da `admin_url` é o erro mais natural que existe.
    A checagem de esquema vinha antes da de credencial e repetia o valor inteiro na mensagem:
    a senha ia para o terminal e para a transcrição do agente."""
    arquivo = tmp_path / "alvos.toml"
    arquivo.write_text('[[alvo]]\nnome = "p"\ntipo = "docker"\ncontext = "p"\n'
                       '[[alvo.componente]]\nnome = "rabbit"\npapel = "fila"\n'
                       f'admin_url = "{url}"\n', encoding="utf-8")

    with pytest.raises(alvos.AlvoInvalido) as erro:
        alvos.ler(arquivo)

    assert "SENHA-REAL-123" not in str(erro.value)


# --- 9. o carregador recusa o que a documentação diz que recusa ---

BASE = """
familia = "exemplo-mgmt"
prioridade = 20

[identificacao]
caminho = "/api/overview"
exige_chaves = ["product_name"]

[[pergunta]]
id = "fila.consumidores_por_fila"
caminho = "CAMINHO"
lista = ""
campos = { nome = "/name", consumidores = "/consumers" }
ordenar_por = "consumidores"
ordem = "desc"
desempate = "nome"
"""


@pytest.mark.parametrize("caminho", [
    "/api/queues/%2F/fila/contents", "/api/queues/%2F/fila/purge",
    "/api/exchanges/%2F/x/publish", "/api/queues/%2F/fila/actions",
    # GET, mas devolvem segredo: definições (hashes de senha, URIs de shovel), usuários,
    # parâmetros (a `src-uri` de um shovel traz usuário e senha), permissões e conexões.
    "/api/definitions", "/api/users", "/api/parameters/shovel", "/api/global-parameters",
    "/api/permissions", "/api/connections",
])
def test_o_carregador_recusa_rota_de_escrita_e_rota_que_devolve_segredo(tmp_path, caminho):
    arquivo = tmp_path / "exemplo-mgmt.toml"
    arquivo.write_text(BASE.replace("CAMINHO", caminho), encoding="utf-8")

    with pytest.raises(CatalogoInvalido):
        carregar_arquivo(arquivo)


def test_o_carregador_recusa_parametro_que_nao_seja_columns(tmp_path):
    arquivo = tmp_path / "exemplo-mgmt.toml"
    arquivo.write_text(BASE.replace("CAMINHO", "/api/queues?disable_stats=true"),
                       encoding="utf-8")

    with pytest.raises(CatalogoInvalido, match="columns"):
        carregar_arquivo(arquivo)


def test_o_carregador_aceita_columns(tmp_path):
    arquivo = tmp_path / "exemplo-mgmt.toml"
    arquivo.write_text(BASE.replace("CAMINHO", "/api/queues?columns=name,consumers"),
                       encoding="utf-8")

    assert carregar_arquivo(arquivo)["familia"] == "exemplo-mgmt"


# --- travas que o juiz provou decorativas ---

def test_get_autenticado_manda_get_no_fio(monkeypatch):
    """O teste por AST só pegava o argumento `method=`; `req.method = "DELETE"` ou trocar
    `get_method` passavam. Este olha o que de fato chega ao opener."""
    from lib.credencial import Credencial

    vistos = []

    class Ok:
        status = 200

        def read(self, n):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(http_get._OPENER, "open",
                        lambda req, timeout=None: vistos.append(req.get_method()) or Ok())
    cred = Credencial(alvo="p", componente="b", usuario="u", senha="s",
                      destino=("exemplo.test", 15672))

    http_get.get_autenticado("http://exemplo.test:15672/api/overview",
                             [("exemplo.test", 15672)], cred, "p")

    assert vistos == ["GET"]


def test_so_credencial_e_runner_leem_o_ambiente():
    """O escopo era só `adaptadores/`; `os.environ` em `lib/extracao.py` passava. A frase da
    documentação é "lida só por `lib/credencial.py`" — o `runner` lê com lista positiva para
    montar o ambiente do processo filho, e é a única outra exceção."""
    permitidos = {"lib/credencial.py", "lib/runner.py"}
    culpados = sorted(str(p.relative_to(SCRIPTS)) for p in SCRIPTS.rglob("*.py")
                      if re.search(r"environ|getenv", p.read_text(encoding="utf-8"))
                      and str(p.relative_to(SCRIPTS)) not in permitidos)

    assert culpados == []


def test_nem_a_senha_em_base64_chega_aos_arquivos(tmp_path, monkeypatch):
    """O teste de ponta a ponta procurava só o texto puro — e o header Basic é justamente
    base64. Gravar `base64(usuario:senha)` no componente passava com a suíte verde."""
    import build_report
    from lib import adaptadores

    senha = "s3gr3do-base64"
    monkeypatch.setenv("SENHA_BROKER", senha)

    def rede(url, permitidos, credencial, alvo=None, timeout=None):
        if url.split("?")[0].endswith("/api/overview"):
            return 200, json.dumps({"product_name": "X", "rabbitmq_version": "4.0"})
        return 200, json.dumps([{"name": "e", "vhost": "/", "messages_ready": 1,
                                 "consumers": 0}])

    monkeypatch.setattr(http_get, "get_autenticado", rede)

    def coletor(alvo, contexto):
        return {"saude": "🟢", "componentes": [
            {"nome": "broker", "papel": "fila", "admin_url": "http://exemplo.test:15672",
             "senha_env": "SENHA_BROKER", "usuario": "leitor"}]}

    for nome, texto in (("default.toml", '[relatorio]\npasta = "x"\n'),
                        ("alvos.toml", '[[alvo]]\nnome = "p"\ntipo = "docker"\ncontext = "p"\n'),
                        ("config.toml", 'alvos = ["p"]\n')):
        (tmp_path / nome).write_text(texto, encoding="utf-8")
    collect.main(["--padrao", str(tmp_path / "default.toml"),
                  "--infra", str(tmp_path / "alvos.toml"),
                  "--projeto", str(tmp_path / "config.toml"), "--out", str(tmp_path / "saida"),
                  "--at", "2026-09-21T10:00:00Z", "--confirmar", "p"],
                 coletores={"docker": coletor}, adaptadores=adaptadores.todos())
    relatorio = json.loads((tmp_path / "saida" / "report.json").read_text(encoding="utf-8"))
    build_report.build(relatorio, tmp_path / "saida", formato="html")

    proibidos = [senha, base64.b64encode(senha.encode()).decode(),
                 base64.b64encode(f"leitor:{senha}".encode()).decode()]
    for arquivo in (tmp_path / "saida").iterdir():
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        for proibido in proibidos:
            assert proibido not in texto, f"{arquivo.name} contém {proibido[:12]}..."
