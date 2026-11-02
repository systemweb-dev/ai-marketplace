"""Filas por dentro do container: comando fixo do catálogo, sem senha, sem shell."""
import json
from pathlib import Path

import pytest

import collect
from lib import catalogo_exec, runner
from lib.adaptadores import REGISTRO, exec_leitura, todos
from lib.dados_blocos import _filas
from lib.orcamento import Prazo

SERVICO = "fila_broker"
ID_CONTAINER = "0123456789ab"
VHOSTS = [{"name": "/"}, {"name": "loja"}]
FILAS = {"/": [{"name": "pedidos", "messages_ready": 42, "messages_unacknowledged": 3, "consumers": 2}],
         "loja": [{"name": "emails", "messages_ready": 7, "messages_unacknowledged": 0, "consumers": 0}]}


class Docker:
    """Responde como o runner, sem processo. Guarda todo comando e passa cada um pela allowlist."""

    def __init__(self, ids=ID_CONTAINER, vhosts=None, filas=None, falhar=None):
        self.ids, self.falhar = ids, falhar or {}
        self.vhosts = json.dumps(VHOSTS) if vhosts is None else vhosts
        self.filas = filas if filas is not None else {k: json.dumps(v) for k, v in FILAS.items()}
        self.vistos, self.chamadas = [], []

    def __call__(self, cmd, timeout, errors=None, context=None):
        from lib.coletores.docker_allowlist import check
        check(cmd)
        self.vistos.append(cmd)
        self.chamadas.append({"timeout": timeout, "context": context})
        verbo = "ps" if cmd[1] == "ps" else cmd[4]
        if verbo in self.falhar:
            if errors is not None:
                errors.append({"cmd": "docker", "reason": self.falhar[verbo]})
            return None
        if verbo == "ps":
            return self.ids
        if verbo == "list_vhosts":
            return self.vhosts
        return self.filas[cmd[cmd.index("-p") + 1]]


def componente(**extra):
    return {"nome": SERVICO, "papel": "fila", "produto": "rabbitmq", "respostas": [], **extra}


def contexto(**extra):
    return {"timeout": 5, "docker_context": "cluster-a", "alvo": "a", "cache": {}, **extra}


@pytest.fixture
def docker(monkeypatch):
    falso = Docker()
    monkeypatch.setattr(runner, "run", falso)
    return falso


def test_vem_por_ultimo_entre_as_fontes():
    assert REGISTRO[exec_leitura.ID]["prioridade"] > max(
        item["prioridade"] for chave, item in REGISTRO.items() if chave != exec_leitura.ID)
    assert todos()[-1] is exec_leitura


def test_fluxo_completo_no_formato_de_hoje(docker):
    r = exec_leitura.perguntar("fila.filas", componente(), contexto())
    assert r["fonte"] == "exec:rabbitmq" and r["identidade"] == ["nome", "vhost"]
    assert r["valor"] == [
        {"nome": "pedidos", "vhost": "/", "prontas": 42, "nao_confirmadas": 3, "consumidores": 2,
         "acumuladas": 45.0, "objeto": "pedidos@/"},
        {"nome": "emails", "vhost": "loja", "prontas": 7, "nao_confirmadas": 0, "consumidores": 0,
         "acumuladas": 7.0, "objeto": "emails@loja"}]
    assert docker.vistos == [
        ["docker", "ps", "--filter", f"label=com.docker.swarm.service.name={SERVICO}", "--format", "{{.ID}}"],
        ["docker", "exec", ID_CONTAINER, "rabbitmqctl", "list_vhosts", "-q", "--formatter", "json", "name"],
        ["docker", "exec", ID_CONTAINER, "rabbitmqctl", "list_queues", "-q", "--formatter", "json", "-p", "/",
         "name", "messages_ready", "messages_unacknowledged", "consumers"],
        ["docker", "exec", ID_CONTAINER, "rabbitmqctl", "list_queues", "-q", "--formatter", "json", "-p", "loja",
         "name", "messages_ready", "messages_unacknowledged", "consumers"]]
    assert {c["context"] for c in docker.chamadas} == {"cluster-a"}


def test_tres_perguntas_leem_o_broker_uma_vez_so(docker):
    c = contexto()
    exec_leitura.perguntar("fila.filas", componente(), c)
    r = exec_leitura.perguntar("fila.consumidores_por_fila", componente(), c)
    assert len(docker.vistos) == 4
    assert r["fonte"] == "exec:rabbitmq"
    assert r["valor"][0] == {"nome": "pedidos", "vhost": "/", "consumidores": 2, "objeto": "pedidos@/"}


def test_taxas_nao_sao_medidas_e_nao_custam_comando(docker):
    r = exec_leitura.perguntar("fila.taxa_entrada_saida", componente(), contexto())
    assert r["sem_dados"] and docker.vistos == []


@pytest.mark.parametrize("comp", [
    {"nome": SERVICO, "papel": "fila", "respostas": []},
    {"nome": SERVICO, "papel": "fila", "produto": "outro-broker", "respostas": []},
    {"nome": SERVICO, "papel": "fila", "produto": None, "respostas": []},
    {"nome": SERVICO, "papel": "fila", "produto": "rabbitmq", "exportador": True, "respostas": []},
])
def test_nunca_exec_em_produto_fora_do_catalogo(docker, comp):
    r = exec_leitura.perguntar("fila.filas", comp, contexto())
    assert r["sem_dados"] and r["nao_se_aplica"] and docker.vistos == []


def test_alvo_sem_context_nao_roda_nada(docker):
    r = exec_leitura.perguntar("fila.filas", componente(), contexto(docker_context=None))
    assert r["sem_dados"] and docker.vistos == []


def test_pergunta_de_outro_papel_nao_roda_nada(docker):
    r = exec_leitura.perguntar("app.cpu", componente(), contexto())
    assert r["nao_se_aplica"] and docker.vistos == []


def test_container_fora_do_no_do_context_tem_motivo_claro(docker):
    docker.ids = "\n"
    r = exec_leitura.perguntar("fila.filas", componente(), contexto())
    assert r["sem_dados"] and "cluster-a" in r["motivo"] and "outro nó" in r["motivo"]
    assert len(docker.vistos) == 1


def test_escolhe_o_mesmo_container_em_qualquer_ordem(docker):
    docker.ids = "ffffffffffff\n0123456789ab\n"
    exec_leitura.perguntar("fila.filas", componente(), contexto())
    assert docker.vistos[1][2] == "0123456789ab"


def test_id_invalido_na_saida_do_ps_nao_vira_argumento(docker):
    docker.ids = "--privileged\nsh\n"
    r = exec_leitura.perguntar("fila.filas", componente(), contexto())
    assert r["sem_dados"] and len(docker.vistos) == 1


def test_nome_de_servico_invalido_nao_chega_ao_docker(docker):
    r = exec_leitura.perguntar("fila.filas", componente(nome="-x y"), contexto())
    assert r["sem_dados"] and docker.vistos == []


@pytest.mark.parametrize("vhosts", ["", "   \n", "nao é json", '{"name": "/"}', "[]", '[{"nome": "/"}]', '["/"]'])
def test_saida_ruim_na_enumeracao_vira_sem_dados(docker, vhosts):
    docker.vhosts = vhosts
    r = exec_leitura.perguntar("fila.filas", componente(), contexto())
    assert r["sem_dados"] and r["motivo"] and len(docker.vistos) == 2


@pytest.mark.parametrize("vhost", ["--help", "a b", "a;id", "$(id)", 7])
def test_vhost_invalido_nao_vira_comando(docker, vhost):
    docker.vhosts = json.dumps([{"name": "/"}, {"name": vhost}])
    r = exec_leitura.perguntar("fila.filas", componente(), contexto())
    assert r["sem_dados"] and "vhost" in r["motivo"] and len(docker.vistos) == 2


@pytest.mark.parametrize("saida", ["", "xyz", '{"a": 1}'])
def test_saida_ruim_na_listagem_vira_sem_dados_sem_lista_pela_metade(docker, saida):
    docker.filas = {"/": json.dumps(FILAS["/"]), "loja": saida}
    r = exec_leitura.perguntar("fila.filas", componente(), contexto())
    assert r["sem_dados"] and "valor" not in r


def test_erro_do_comando_vira_motivo_redigido(docker):
    docker.falhar = {"list_vhosts": "falhou em amqp://leitor:segredo@broker"}
    r = exec_leitura.perguntar("fila.filas", componente(), contexto())
    assert r["sem_dados"] and "segredo" not in r["motivo"] and "falhou" in r["motivo"]


def test_erro_do_ps_vira_motivo(docker):
    docker.falhar = {"ps": "daemon fora"}
    r = exec_leitura.perguntar("fila.filas", componente(), contexto())
    assert r["sem_dados"] and "daemon fora" in r["motivo"]


def test_a_falha_fica_no_cache_e_nao_repete_comando(docker):
    docker.falhar = {"list_vhosts": "x"}
    c = contexto()
    exec_leitura.perguntar("fila.filas", componente(), c)
    r = exec_leitura.perguntar("fila.consumidores_por_fila", componente(), c)
    assert r["sem_dados"] and len(docker.vistos) == 2


def test_prazo_esgotado_nao_roda_nada(docker):
    r = exec_leitura.perguntar("fila.filas", componente(), contexto(prazo=Prazo(0)))
    assert r["sem_dados"] and r["motivo"] == Prazo.motivo() and docker.vistos == []


def test_prazo_que_acaba_no_meio_para_entre_comandos(docker):
    instantes = iter([0, 0, 0, 0, 0, 100])
    prazo = Prazo(10, agora=lambda: next(instantes, 100))
    r = exec_leitura.perguntar("fila.filas", componente(), contexto(prazo=prazo))
    assert r["sem_dados"] and r["motivo"] == Prazo.motivo()
    assert 1 <= len(docker.vistos) < 4


def test_cada_comando_pede_so_o_tempo_que_resta(docker):
    relogio = [0.0]
    prazo = Prazo(3, agora=lambda: relogio[0])
    exec_leitura.perguntar("fila.filas", componente(), contexto(prazo=prazo))
    assert {c["timeout"] for c in docker.chamadas} == {3}


def test_responder_entrega_prazo_e_limiar_funciona(docker):
    comp = componente()
    collect.responder(comp, contexto(), [exec_leitura], Prazo(30))
    respostas = {r["pergunta"]: r for r in comp["respostas"]}
    assert respostas["fila.filas"]["fonte"] == "exec:rabbitmq"
    assert respostas["fila.taxa_entrada_saida"]["sem_dados"]
    assert [(a["regra"], a["objeto"]) for a in comp["achados"]] == [("fila_sem_consumidor", "emails@loja")]


def test_as_fontes_com_senha_e_exporter_vencem(docker):
    class Admin:
        ID = "admin_http"

        @staticmethod
        def perguntar(pergunta, componente, contexto):
            return {"pergunta": pergunta, "fonte": "admin_http:x", "valor": [{"nome": "a", "prontas": 1, "consumidores": 1}]}

    comp = componente()
    collect.responder(comp, contexto(), [Admin, exec_leitura], Prazo(30))
    assert docker.vistos == []


def test_ritmo_segue_nao_medido_no_bloco(docker):
    comp = componente()
    collect.responder(comp, contexto(), [exec_leitura], Prazo(30))
    filas = _filas([{"coletado": True, "componentes": [comp]}])["filas"]
    assert all(f["ritmo_nao_medido"] for f in filas)


def test_coletar_alvo_entrega_o_context_e_a_cobertura_fica_medida(docker):
    def coletor(alvo, contexto_):
        return {"saude": "🟢", "componentes": [componente()]}

    alvo = {"nome": "a", "tipo": "docker", "context": "cluster-a"}
    registro = collect.coletar_alvo(alvo, coletor, {"timeout": 5}, [exec_leitura])
    assert registro["componentes"][0]["respostas"][0]["fonte"] == "exec:rabbitmq"
    assert {c["context"] for c in docker.chamadas} == {"cluster-a"}


def test_coletor_docker_marca_o_produto_pelo_caminho_da_imagem():
    from lib import produtos
    assert produtos.nome_do_caminho("library/rabbitmq") == "rabbitmq"
    assert produtos.nome_do_caminho("minha/app-rabbitmq-worker:1") == "rabbitmq"
    assert produtos.nome_do_caminho("exemplo/api") is None
    assert produtos.nome_do_caminho(None) is None


def test_componente_do_coletor_carrega_produto(monkeypatch):
    from lib.coletores import docker as coletor

    bruto = {"services": [{"name": SERVICO, "image": "rabbitmq", "tag": "4.0", "replicas": "1/1"},
                          {"name": "loja_api", "image": "exemplo/api", "tag": "1", "replicas": "1/1"}]}
    monkeypatch.setattr(coletor, "assemble_report", lambda **k: bruto)
    monkeypatch.setattr(coletor, "contexto_existe", lambda *a, **k: True, raising=False)
    r = coletor.coletar({"nome": "a", "tipo": "docker", "context": "c"}, {"timeout": 5})
    por_nome = {c["nome"]: c for c in r["componentes"]}
    assert por_nome[SERVICO]["produto"] == "rabbitmq"
    assert por_nome["loja_api"]["produto"] is None


# --- o catálogo ---

def _escrever(tmp_path, **troca):
    base = {"familia": "rabbitmq",
            "enumerar_argv": '["rabbitmqctl", "list_vhosts", "-q"]', "campo": '"name"',
            "listar_argv": '["rabbitmqctl", "list_queues", "-p", "{vhost}", "name"]'}
    base.update(troca)
    arquivo = tmp_path / "f.toml"
    arquivo.write_text(f'''familia = "{base["familia"]}"
[enumerar]
argv = {base["enumerar_argv"]}
campo = {base["campo"]}
[listar]
argv = {base["listar_argv"]}
{base.get("extra", "")}
''', encoding="utf-8")
    return arquivo


def test_arquivo_minimo_passa(tmp_path):
    assert catalogo_exec.carregar_arquivo(_escrever(tmp_path))["familia"] == "rabbitmq"


@pytest.mark.parametrize("troca", [
    {"familia": "desconhecido"},
    {"enumerar_argv": '["sh", "-c", "id"]'},
    {"enumerar_argv": '["bash", "list_vhosts"]'},
    {"enumerar_argv": '["/bin/rabbitmqctl", "list_vhosts"]'},
    {"enumerar_argv": '["rabbitmqctl", "delete_vhost", "x"]'},
    {"enumerar_argv": '["rabbitmqctl"]'},
    {"enumerar_argv": '[]'},
    {"enumerar_argv": '["rabbitmqctl", "list_vhosts", "-it"]'},
    {"enumerar_argv": '["rabbitmqctl", "list_vhosts", "a;b"]'},
    {"enumerar_argv": '["rabbitmqctl", "list_vhosts", "{vhost}"]'},
    {"listar_argv": '["rabbitmqctl", "list_queues", "name"]'},
    {"listar_argv": '["rabbitmqctl", "list_queues", "{vhost}", "{vhost}"]'},
    {"listar_argv": '["rabbitmqctl", "purge_queue", "{vhost}"]'},
    {"extra": '[[pergunta]]\nid = "nao.existe"\nlista = ""\ncampos = { a = "/a" }\n'},
    {"extra": '[[pergunta]]\nid = "fila.filas"\nlista = ""\ncampos = { nome = "/name" }\n'},
    {"extra": '[[pergunta]]\nid = "fila.filas"\nlista = ""\nlimite = 3\ncampos = { prontas = "/a", consumidores = "/b" }\n'},
    {"extra": 'shell = true\n'},
])
def test_catalogo_recusa_o_que_nao_e_leitura_fixa(tmp_path, troca):
    with pytest.raises(catalogo_exec.CatalogoInvalido):
        catalogo_exec.carregar_arquivo(_escrever(tmp_path, **troca))


def test_o_catalogo_publicado_passa_e_nao_mede_taxa():
    familia = next(f for f in catalogo_exec.familias() if f["familia"] == "rabbitmq")
    assert {p["id"] for p in familia["pergunta"]} == {"fila.filas", "fila.consumidores_por_fila"}


def test_a_pasta_do_catalogo_e_references_execs():
    raiz = Path(__file__).resolve().parents[1]
    assert catalogo_exec.PASTA == raiz / "references" / "execs"
    assert (catalogo_exec.PASTA / "rabbitmq.toml").exists()


def test_skill_troca_a_garantia_de_exec():
    texto = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    assert "`exec` só para leitura, comando fixo do catálogo, sem shell" in texto
    assert "`logs`, `cp`, `secret inspect`" in texto and "rm/kill/restart/exec" not in texto
    assert "| `exec_leitura` |" in texto
