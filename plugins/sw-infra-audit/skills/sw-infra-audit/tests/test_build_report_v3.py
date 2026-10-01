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
    # o diagnostico comeca na primeira faixa de acao; antes dela so vem o inventario
    assert html.index("context: ctx") < html.index('id="faixa-1"'), \
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

    assert html.count('id="faixa-3"') == 1, "a seção existe uma vez só"
    assert "%%ALVOS%%" in html, "o marcador aparece como texto, não como seção"


def test_relatorio_v2_e_recusado_com_mensagem_que_explica(tmp_path):
    """Sem migração silenciosa: o relatório antigo fica onde está, como histórico."""
    import pytest
    v2 = {"schema_version": 2, "generated_at": "2026-09-19T10:00:00Z", "alvos": []}
    with pytest.raises(ValueError) as erro:
        build_report.build(v2, tmp_path)
    assert "v3" in str(erro.value) and "histórico" in str(erro.value)


def test_html_sozinho_quando_o_pdf_nao_foi_pedido(tmp_path, monkeypatch):
    """O HTML é o produto; o PDF é uma escolha de quem recebe. Gerar PDF sempre custa alguns
    segundos de Chromium em toda rodada, inclusive quando ninguém vai imprimir."""
    chamou = []
    monkeypatch.setattr(build_report, "find_chromium", lambda: chamou.append(1) or "/bin/false")
    relatorio = {"schema_version": 3, "generated_at": "2026-09-19T10:00:00Z", "alvos": [],
                 "inventario": [], "aceites": [], "historico": None, "resumo": "",
                 "fortes": [], "fracos": [], "recomendacoes": []}

    res = build_report.build(relatorio, tmp_path, formato="html")

    assert (tmp_path / "relatorio.html").exists()
    assert res["pdf"] is None
    assert chamou == [], "nem procurou o Chromium"


def test_formato_desconhecido_e_recusado(tmp_path):
    import pytest
    relatorio = {"schema_version": 3, "generated_at": "x", "alvos": [], "inventario": [],
                 "aceites": [], "historico": None, "resumo": "", "fortes": [], "fracos": [],
                 "recomendacoes": []}
    with pytest.raises(ValueError) as erro:
        build_report.build(relatorio, tmp_path, formato="docx")
    assert "docx" in str(erro.value)


def _com_cluster():
    """Relatório com os fatos que a coleta já traz e o v3 não desenhava."""
    dados = relatorio()
    dados["alvos"][0]["fatos"] = {
        "nodes": [{"hostname": "no-1", "role": "manager", "leader": True, "state": "ready",
                   "availability": "active", "engine": "25.0", "platform": "linux/x86_64",
                   "capacity": {"nano_cpus": 4_000_000_000, "mem_bytes": 8_589_934_592},
                   "tasks_running": 12, "tasks_failed": 0, "failed_examples": []},
                  {"hostname": "no-2", "role": "worker", "leader": False, "state": "ready",
                   "availability": "active", "engine": "24.0", "platform": "linux/x86_64",
                   "capacity": {"nano_cpus": 2_000_000_000, "mem_bytes": 4_294_967_296},
                   "tasks_running": 7, "tasks_failed": 1,
                   "failed_examples": ['loja_api.3: "task: non-zero exit (137)"']}],
        "disk": [{"tipo": "Images", "total": 42, "ativo": 12, "tamanho": "9GB",
                  "recuperavel": "4GB"}],
        "networks": [{"name": "traefik-public", "driver": "overlay", "scope": "swarm"}],
        "secrets": [{"name": "senha_do_banco"}],
        "tls": {"verify": True, "ca": "ca.pem",
                "certs": [{"file": "cert.pem", "label": "cliente", "status": "expiring",
                           "not_after": "2026-11-02T00:00:00Z", "days_left": 34}]},
        "stacks": [{"stack": "loja", "services": [
            {"name": "loja_web", "image": "nginx", "tag": "1.27", "kind": "ingress",
             "has_healthcheck": True, "limits": {"nano_cpus": 1_000_000_000}},
            {"name": "loja_api", "image": "app", "tag": "2.1", "kind": "app",
             "has_healthcheck": False, "limits": {}}],
            "findings_high": 1, "findings_med": 0, "has_ingress": True,
            "kinds": ["ingress", "app"], "spofs": ["loja_api"], "note": "red",
            "routes": ["loja.exemplo.test"]}],
    }
    return dados


def test_relatorio_mostra_os_nos_do_cluster(tmp_path):
    """A coleta traz os nós desde sempre; o v3 guardava e não desenhava."""
    html = montar(tmp_path, _com_cluster())

    assert "no-1" in html and "no-2" in html
    assert "25.0" in html and "24.0" in html, "engine por nó permite ver o nó desatualizado"
    assert "exit 137" in html, "a falha recente do nó é o que explica o alerta"
    assert "SIGKILL" in html, "o código sozinho não diz nada; a pista é o que o leitor usa"


def test_relatorio_mostra_disco_redes_e_secrets(tmp_path):
    html = montar(tmp_path, _com_cluster())

    assert "4GB" in html, "o recuperável é o número que leva à ação"
    assert "traefik-public" in html
    assert "senha_do_banco" in html, "o NOME do secret é inventário; o valor nunca é coletado"
    assert "cert.pem" in html and "34 dias" in html, "certificado perto de vencer é achado com data"


def test_tls_sem_certificado_nao_vira_tabela_so_com_cabecalho(tmp_path):
    """O alvo pode ter TLS ligado e nenhum certificado legível — aí a tabela vazia só
    ocupa espaço prometendo dado que não existe."""
    dados = _com_cluster()
    dados["alvos"][0]["fatos"]["tls"] = {"verify": True, "ca": "ca.pem", "certs": []}

    html = montar(tmp_path, dados)

    assert "Certificados TLS" not in html


def test_relatorio_agrupa_por_aplicacao_com_as_rotas(tmp_path):
    """'Como o traefik está roteando pro app X' é a pergunta que a descrição promete."""
    html = montar(tmp_path, _com_cluster())

    assert "loja" in html and "loja.exemplo.test" in html
    # dentro do bloco da stack o serviço aparece com o nome curto: `loja_web` vira `web`
    assert ">web<" in html and ">api<" in html
    assert "sem limites" in html, "o sinal por serviço é o que justifica olhar a aplicação"
    assert "1 crítico<" in html, "selo no singular: '1 críticos' entrega relatório gerado no braço"


def test_alvo_sem_esses_fatos_nao_ganha_secao_vazia(tmp_path):
    """Alvo HTTP não tem nó nem stack: a seção não pode aparecer prometendo vazio."""
    html = montar(tmp_path)

    assert "Nenhum nó" not in html and "nenhuma aplicação" not in html.lower()
