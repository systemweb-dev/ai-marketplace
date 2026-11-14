import json

from apoio_host import Falha, runner_falso
from apoio_produto import MARIADB, PERGUNTA_DE_LISTA, QDRANT, gravar
from lib.adaptadores import produto_ssh

COMP = {"nome": "mariadb", "papel": "banco", "produto": "mariadb", "leitura": "socket",
        "origem": "unidade:mariadb.service", "ssh_destino": "root@banco-01", "porta": None}
SAIDAS = {"SHOW GLOBAL STATUS": "Threads_connected\t12\nSlow_queries\t7\n",
          "SELECT SUM(data_length + index_length) FROM information_schema.tables": "734003200\n"}


def _ctx():
    return {"timeout": 20, "cache": {}, "alvo": "banco-01", "at": "2026-11-13T10:00:00Z"}


def _perguntar(monkeypatch, pergunta, componente, saidas, **opcoes):
    monkeypatch.setattr(produto_ssh.runner, "run_ssh", runner_falso(saidas, **opcoes))
    return produto_ssh.perguntar(pergunta, componente, _ctx())


def test_socket_responde_conexoes_e_tamanho(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    assert _perguntar(monkeypatch, "banco.conexoes", COMP, SAIDAS) == {
        "pergunta": "banco.conexoes", "fonte": "ssh:mariadb", "valor": 12}
    assert _perguntar(monkeypatch, "banco.tamanho", COMP, SAIDAS)["valor"] == 734003200


def test_a_mesma_consulta_roda_uma_vez_para_duas_perguntas(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    chamadas = []
    monkeypatch.setattr(produto_ssh.runner, "run_ssh", runner_falso(SAIDAS, chamadas=chamadas))
    contexto = _ctx()
    produto_ssh.perguntar("banco.conexoes", COMP, contexto)
    produto_ssh.perguntar("banco.conexoes", COMP, contexto)
    assert chamadas == ["SHOW GLOBAL STATUS"]


def test_sem_leitura_declarada_diz_o_comando_e_explica_a_falta(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    resposta = _perguntar(monkeypatch, "banco.conexoes", {**COMP, "leitura": None}, SAIDAS)
    assert resposta["sem_dados"] and resposta["explica_a_falta"]
    assert "leitura não declarada" in resposta["motivo"] and "configurar.py leitura" in resposta["motivo"]


def test_leitura_nenhum_e_escolha_do_dono_e_nao_conta_como_lacuna(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    resposta = _perguntar(monkeypatch, "banco.conexoes", {**COMP, "leitura": "nenhum"}, SAIDAS)
    assert resposta["sem_dados"] and resposta["nao_publica"]


def test_erro_conhecido_do_catalogo_vira_o_motivo_dele(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    saidas = {"SHOW GLOBAL STATUS": Falha("ERROR 1698 (28000): Access denied for user "
                                          "'root'@'localhost'")}
    resposta = _perguntar(monkeypatch, "banco.conexoes", COMP, saidas)
    assert resposta["motivo"].startswith('o root não entra pelo socket: declare leitura = "senha"')


def test_erro_marcado_no_catalogo_sai_como_nao_medido_por_desenho(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    saidas = {"SHOW GLOBAL STATUS": Falha("ERROR 1381 (HY000): You are not using binary logging")}
    resposta = _perguntar(monkeypatch, "banco.conexoes", COMP, saidas)
    assert resposta["nao_publica"] and "binlog está desligado" in resposta["motivo"]


def test_cliente_ausente_e_o_codigo_127(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    saidas = {"SHOW GLOBAL STATUS": Falha("bash: mariadb: command not found", 127)}
    resposta = _perguntar(monkeypatch, "banco.conexoes", COMP, saidas)
    assert resposta["motivo"] == "o cliente de mariadb não está instalado onde o comando roda"


def test_erro_desconhecido_nao_repete_o_usuario(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    saidas = {"SHOW GLOBAL STATUS": Falha("ERROR 1227 (42000): Access denied for 'leitor'@'%'")}
    resposta = _perguntar(monkeypatch, "banco.conexoes", COMP, saidas)
    assert resposta["sem_dados"] and "leitor" not in resposta["motivo"]
    assert resposta["motivo"].startswith("o cliente de mariadb saiu com erro:")


def test_senha_vai_pela_entrada_e_nunca_pelas_vagas(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    monkeypatch.setenv("SENHA_DO_BANCO_TESTE", "MARCA-123")
    componente = {**COMP, "leitura": "senha", "usuario": "leitor",
                  "senha_env": "SENHA_DO_BANCO_TESTE"}
    registro = []
    resposta = _perguntar(monkeypatch, "banco.conexoes", componente, SAIDAS, registro=registro)
    assert resposta["valor"] == 12
    assert registro[0]["comando"] == 'mariadb --defaults-extra-file=/dev/stdin -N -B -e "{sql}"'
    assert registro[0]["entrada"] == '[client]\nuser="leitor"\npassword="MARCA-123"\n'
    assert "MARCA-123" not in json.dumps(registro[0]["vagas"]) and "MARCA-123" not in json.dumps(resposta)


def test_senha_recusada_pelo_banco(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    monkeypatch.setenv("SENHA_DO_BANCO_TESTE", "MARCA-123")
    componente = {**COMP, "leitura": "senha", "usuario": "leitor",
                  "senha_env": "SENHA_DO_BANCO_TESTE"}
    saidas = {"SHOW GLOBAL STATUS": Falha("ERROR 1045 (28000): Access denied for user 'leitor'")}
    resposta = _perguntar(monkeypatch, "banco.conexoes", componente, saidas)
    assert resposta["motivo"] == "o banco recusou o usuário e a senha declarados"


def test_variavel_de_senha_ausente_nao_repete_o_usuario(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    monkeypatch.delenv("SENHA_AUSENTE_TESTE", raising=False)
    componente = {**COMP, "leitura": "senha", "usuario": "leitor", "senha_env": "SENHA_AUSENTE_TESTE"}
    resposta = _perguntar(monkeypatch, "banco.conexoes", componente, SAIDAS)
    assert "não está no ambiente" in resposta["motivo"] and "leitor" not in resposta["motivo"]


def test_produto_sem_cliente_com_senha_fica_para_depois(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, qdrant=QDRANT)
    componente = {**COMP, "nome": "qdrant", "papel": "busca", "produto": "qdrant",
                  "leitura": "senha", "usuario": "x", "senha_env": "Y"}
    resposta = _perguntar(monkeypatch, PERGUNTA_DE_LISTA, componente, {})
    assert "fica para uma próxima versão" in resposta["motivo"]


def test_leitura_container_exige_origem_container(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    resposta = _perguntar(monkeypatch, "banco.conexoes", {**COMP, "leitura": "container"}, SAIDAS)
    assert "precisa de componente com origem container:" in resposta["motivo"]


def test_leitura_container_passa_o_nome_do_container(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    componente = {**COMP, "leitura": "container", "origem": "container:banco-exemplo"}
    registro = []
    assert _perguntar(monkeypatch, "banco.conexoes", componente, SAIDAS, registro=registro)["valor"] == 12
    assert registro[0]["vagas"] == {"container": "banco-exemplo", "sql": "SHOW GLOBAL STATUS"}


def test_banco_de_host_sem_catalogo_diz_que_falta_catalogo(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    componente = {**COMP, "nome": "mongo", "produto": "mongo"}
    resposta = _perguntar(monkeypatch, "banco.conexoes", componente, {})
    assert resposta["motivo"] == "não medido: falta catálogo ou exporter para mongo"
    assert _perguntar(monkeypatch, "servico.ativo", componente, {})["nao_se_aplica"]


def test_componente_sem_origem_nao_e_deste_adaptador(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, mariadb=MARIADB)
    assert _perguntar(monkeypatch, "banco.conexoes", {**COMP, "origem": None}, SAIDAS)["nao_se_aplica"]


COLECOES = json.dumps({"result": {"collections": [{"name": "docs"}, {"name": "a;b"},
                                                  {"name": "x y"}, {"name": "faq"}]}})


def test_colecao_fora_do_formato_e_pulada_e_dita(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, qdrant=QDRANT)
    componente = {**COMP, "nome": "qdrant", "papel": "busca", "produto": "qdrant",
                  "origem": "unidade:qdrant.service", "portas": [6333, 6334]}
    saidas = {"/collections": COLECOES,
              "/collections/docs": json.dumps({"result": {"points_count": 1200}}),
              "/collections/faq": json.dumps({"result": {"points_count": 30}})}
    chamadas, registro = [], []
    resposta = _perguntar(monkeypatch, PERGUNTA_DE_LISTA, componente, saidas, chamadas=chamadas,
                          registro=registro)
    assert resposta["valor"] == [{"nome": "docs", "pontos": 1200}, {"nome": "faq", "pontos": 30}]
    assert resposta["nota"].startswith("2 item(ns) com nome fora do formato")
    assert chamadas == ["/collections", "/collections/docs", "/collections/faq"]
    assert {r["vagas"]["porta"] for r in registro} == {6333}


def test_erro_por_codigo_do_qdrant(tmp_path, monkeypatch):
    gravar(tmp_path, monkeypatch, qdrant=QDRANT)
    componente = {**COMP, "nome": "qdrant", "papel": "busca", "produto": "qdrant"}
    resposta = _perguntar(monkeypatch, PERGUNTA_DE_LISTA, componente,
                          {"/collections": Falha("", 22)})
    assert resposta["motivo"] == "o Qdrant recusou a leitura (pede chave de API?)"
