# tests/test_collect_orquestrador.py
import json

import pytest

import collect


def ambiente(tmp_path, projeto='alvos = ["cluster", "site"]\n'):
    (tmp_path / "default.toml").write_text(
        '[relatorio]\npasta = "docs/infra"\n[limites]\ntimeout_por_comando = 5\n'
        'orcamento_por_alvo = 10\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "cluster"\ntipo = "docker"\ncontext = "ctx"\n\n'
        '[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://127.0.0.1:1/health"\n',
        encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text(projeto, encoding="utf-8")
    return ["--padrao", str(tmp_path / "default.toml"),
            "--infra", str(tmp_path / "alvos.toml"),
            "--projeto", str(tmp_path / ".sw-infra-audit.toml"),
            "--out", str(tmp_path / "saida"), "--at", "2026-09-19T10:00:00Z"]


def coletor_falso(registro, saude="🟢"):
    def coletar(alvo, contexto):
        registro.append(alvo["nome"])
        return {"saude": saude, "fatos": {"ok": True},
                "achados": [{"regra": "r1", "objeto": alvo["nome"], "severidade": "low",
                             "alvo": alvo["nome"]}]}
    return coletar


def ler_relatorio(tmp_path):
    return json.loads((tmp_path / "saida" / "report.json").read_text(encoding="utf-8"))


def test_so_o_alvo_confirmado_e_coletado(tmp_path):
    visitados = []
    coletores = {"docker": coletor_falso(visitados), "http": coletor_falso(visitados)}

    codigo = collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)

    assert codigo == 0
    assert visitados == ["cluster"], "site não foi confirmado: não pode ser tocado"


def test_alvo_nao_confirmado_aparece_no_relatorio_como_sem_dados(tmp_path):
    coletores = {"docker": coletor_falso([]), "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    r = ler_relatorio(tmp_path)

    site = next(a for a in r["alvos"] if a["nome"] == "site")
    assert site["saude"] == "sem dados"
    assert any("confirmad" in n["motivo"] for n in site["nao_coletado"])


def test_sem_confirmar_nada_nenhum_coletor_roda(tmp_path, capsys):
    visitados = []
    coletores = {"docker": coletor_falso(visitados), "http": coletor_falso(visitados)}

    codigo = collect.main(ambiente(tmp_path), coletores=coletores)

    assert codigo == 2
    assert visitados == []
    assert "confirm" in capsys.readouterr().err


def test_confirmar_alvo_que_nao_existe_para_antes_de_coletar(tmp_path, capsys):
    visitados = []
    coletores = {"docker": coletor_falso(visitados), "http": coletor_falso(visitados)}

    codigo = collect.main([*ambiente(tmp_path), "--confirmar", "fantasma"], coletores=coletores)

    assert codigo == 2 and visitados == []
    assert "fantasma" in capsys.readouterr().err


def test_relatorio_sai_com_inventario_e_ordem_declarada(tmp_path):
    coletores = {"docker": coletor_falso([]), "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster", "site"], coletores=coletores)
    r = ler_relatorio(tmp_path)

    assert [a["nome"] for a in r["alvos"]] == ["cluster", "site"]
    assert [i["nome"] for i in r["inventario"]] == ["cluster", "site"]
    assert r["generated_at"] == "2026-09-19T10:00:00Z"
    assert r["schema_version"] == 3


def test_coletor_que_estoura_o_orcamento_vira_sem_dados_sem_derrubar_o_resto(tmp_path):
    def lento(alvo, contexto):
        raise TimeoutError("passou do orçamento")

    coletores = {"docker": lento, "http": coletor_falso([])}

    codigo = collect.main([*ambiente(tmp_path), "--confirmar", "cluster", "site"],
                          coletores=coletores)
    r = ler_relatorio(tmp_path)

    assert codigo == 0, "um alvo travado não derruba a auditoria inteira"
    cluster = next(a for a in r["alvos"] if a["nome"] == "cluster")
    site = next(a for a in r["alvos"] if a["nome"] == "site")
    assert cluster["saude"] == "sem dados" and "orçamento" in cluster["nao_coletado"][0]["motivo"]
    assert site["saude"] == "🟢"


def test_falha_do_coletor_nao_vira_achado(tmp_path):
    def quebrado(alvo, contexto):
        raise RuntimeError("conexão recusada")

    coletores = {"docker": quebrado, "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    cluster = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert cluster["achados"] == [], "não consegui ver ≠ está ruim"
    assert "conexão recusada" in cluster["nao_coletado"][0]["motivo"]


def test_nada_e_escrito_fora_da_pasta_de_saida(tmp_path):
    coletores = {"docker": coletor_falso([]), "http": coletor_falso([])}
    args = ambiente(tmp_path)                 # cria a configuração ANTES do retrato
    antes = {p for p in tmp_path.rglob("*")}

    collect.main([*args, "--confirmar", "cluster"], coletores=coletores)

    novos = {p for p in tmp_path.rglob("*")} - antes
    assert all(str(p).startswith(str(tmp_path / "saida")) for p in novos), sorted(map(str, novos))


def test_coletor_que_devolve_lixo_nao_derruba_a_auditoria(tmp_path):
    """Coletor com bug devolvendo None não pode impedir o relatório dos outros alvos."""
    coletores = {"docker": lambda alvo, ctx: None, "http": coletor_falso([])}

    codigo = collect.main([*ambiente(tmp_path), "--confirmar", "cluster", "site"],
                          coletores=coletores)
    r = ler_relatorio(tmp_path)

    assert codigo == 0
    cluster = next(a for a in r["alvos"] if a["nome"] == "cluster")
    assert cluster["saude"] == "sem dados" and cluster["nao_coletado"]
    assert next(a for a in r["alvos"] if a["nome"] == "site")["saude"] == "🟢"


def test_coletor_nao_pode_reescrever_a_identidade_do_alvo(tmp_path):
    """Se pudesse, o inventário mentiria e a chave de histórico trocaria de dono."""
    def mentiroso(alvo, contexto):
        return {"nome": "outro", "tipo": "http", "onde": "usuario:senha@host",
                "saude": "🟢", "fatos": {}, "achados": []}

    coletores = {"docker": mentiroso, "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    cluster = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert cluster["tipo"] == "docker"
    assert cluster["onde"] == "context: ctx"
    assert "senha" not in json.dumps(ler_relatorio(tmp_path))


def test_achados_de_tipo_errado_viram_sem_dados(tmp_path):
    coletores = {"docker": lambda alvo, ctx: {"saude": "🟢", "achados": "isto devia ser lista"},
                 "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    cluster = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert cluster["achados"] == []
    assert any("inválid" in n["motivo"] for n in cluster["nao_coletado"])


def test_erro_de_programacao_no_coletor_fica_marcado_como_tal(tmp_path):
    """"Não consegui conectar" e "o coletor tem bug" precisam ser distinguíveis."""
    def bugado(alvo, contexto):
        return {"saude": alvo["campo_que_nao_existe"]}

    coletores = {"docker": bugado, "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    cluster = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert cluster["erro_interno"] is True
    assert "KeyError" in cluster["nao_coletado"][0]["motivo"]


def test_falha_esperada_de_coleta_nao_e_erro_interno(tmp_path):
    from lib.falhas import FalhaDeColeta

    def recusado(alvo, contexto):
        raise FalhaDeColeta("conexão recusada")

    coletores = {"docker": recusado, "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"], coletores=coletores)
    cluster = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert cluster.get("erro_interno") is not True
    assert cluster["nao_coletado"][0]["motivo"] == "conexão recusada"


def test_sem_alvos_toml_o_usuario_e_mandado_para_o_migrar(tmp_path, capsys):
    (tmp_path / "default.toml").write_text('[limites]\ntimeout_por_comando = 5\n',
                                           encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text("alvos = []\n", encoding="utf-8")
    args = ["--padrao", str(tmp_path / "default.toml"),
            "--infra", str(tmp_path / "nao-existe.toml"),
            "--projeto", str(tmp_path / ".sw-infra-audit.toml"),
            "--out", str(tmp_path / "saida"), "--at", "2026-09-19T10:00:00Z"]

    codigo = collect.main([*args, "--confirmar", "qualquer"], coletores={})
    saida = capsys.readouterr()

    assert codigo == 2
    assert "migrar" in (saida.out + saida.err)


@pytest.mark.parametrize("confirmar", [[], [""], ["CLUSTER"], ["cluster extra"], ["site"]])
def test_gate_recusa_confirmacao_que_nao_casa_exatamente(tmp_path, confirmar):
    """`site` está no alvos.toml mas fora da seleção do projeto: confirmar não o traz de volta."""
    visitados = []
    coletores = {"docker": coletor_falso(visitados), "http": coletor_falso(visitados)}
    projeto = 'alvos = ["cluster"]\n'

    codigo = collect.main([*ambiente(tmp_path, projeto=projeto), "--confirmar", *confirmar],
                          coletores=coletores)

    assert codigo == 2 and visitados == []


def test_escrita_confinada_pega_sobrescrita_de_arquivo_existente(tmp_path, monkeypatch):
    """Comparar só a lista de caminhos deixaria passar sobrescrita de arquivo que já existia."""
    import hashlib

    def retrato():
        return {str(p.relative_to(tmp_path)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in tmp_path.rglob("*") if p.is_file()}

    coletores = {"docker": coletor_falso([]), "http": coletor_falso([])}
    args = ambiente(tmp_path)
    monkeypatch.chdir(tmp_path)
    antes = retrato()

    collect.main([*args, "--confirmar", "cluster"], coletores=coletores)

    mexidos = {c for c in set(antes) | set(retrato()) if antes.get(c) != retrato().get(c)}
    assert all(c.startswith("saida/") for c in mexidos), sorted(mexidos)


def test_carimbo_de_tempo_invalido_para_antes_de_coletar(tmp_path, capsys):
    """O carimbo vira a data que decide aceite vencido: aceitar lixo aqui é silenciar aceites."""
    visitados = []
    coletores = {"docker": coletor_falso(visitados), "http": coletor_falso(visitados)}
    args = [a if a != "2026-09-19T10:00:00Z" else "ontem" for a in ambiente(tmp_path)]

    codigo = collect.main([*args, "--confirmar", "cluster"], coletores=coletores)

    assert codigo == 2 and visitados == []
    assert "--at" in capsys.readouterr().err


def test_aceite_do_projeto_tira_o_achado_da_nota(tmp_path):
    """Integração: o aceite configurado no projeto precisa chegar ao relatório final."""
    projeto = ('alvos = ["cluster"]\n\n[[aceite]]\nalvo = "cluster"\nregra = "r1"\n'
               'motivo = "risco assumido"\ndesde = "2026-01-01"\nrevisar_em = "2027-01-01"\n')
    coletores = {"docker": coletor_falso([]), "http": coletor_falso([])}

    collect.main([*ambiente(tmp_path, projeto=projeto), "--confirmar", "cluster"],
                 coletores=coletores)
    r = ler_relatorio(tmp_path)

    cluster = next(a for a in r["alvos"] if a["nome"] == "cluster")
    assert cluster["achados"] == []
    assert r["aceites"][0]["motivo"] == "risco assumido" and r["aceites"][0]["origem"] == "projeto"


def test_sem_registro_explicito_a_skill_usa_os_coletores_de_verdade(tmp_path, monkeypatch):
    """Rodando pela linha de comando ninguém passa `coletores`: se o registro padrão não existir,
    a auditoria devolve "sem coletor nesta versão" para tudo — e foi o que aconteceu."""
    padrao = collect.coletores_padrao()
    assert set(padrao) == {"docker", "http"} and all(callable(f) for f in padrao.values())

    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://127.0.0.1:1/x"\n', encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = ["site"]\n', encoding="utf-8")
    (tmp_path / "default.toml").write_text(
        '[relatorio]\npasta = "docs/infra"\n[limites]\ntimeout_por_comando = 5\n'
        'orcamento_por_alvo = 10\nhttp_timeout = 1\n', encoding="utf-8")
    args = ["--padrao", str(tmp_path / "default.toml"), "--infra", str(tmp_path / "alvos.toml"),
            "--projeto", str(tmp_path / ".sw-infra-audit.toml"),
            "--out", str(tmp_path / "saida"), "--at", "2026-09-19T10:00:00Z"]

    collect.main([*args, "--confirmar", "site"])          # sem `coletores=`
    site = json.loads((tmp_path / "saida" / "report.json").read_text(encoding="utf-8"))["alvos"][0]

    motivos = " ".join(n["motivo"] for n in site["nao_coletado"])
    assert "sem coletor" not in motivos, motivos
    assert "não consegui alcançar" in motivos, "o coletor http rodou de verdade e não alcançou"



def test_aceite_com_data_impossivel_para_a_auditoria_com_mensagem(tmp_path, capsys):
    """Data inválida no aceite não pode virar traceback: o usuário precisa saber QUAL linha
    arrumar, e a auditoria para antes de gravar um relatório pela metade."""
    projeto = ('alvos = ["cluster"]\n\n[[aceite]]\nalvo = "cluster"\nregra = "r1"\n'
               'motivo = "risco assumido"\ndesde = "2026-03-31"\nrevisar_em = "2026-09-31"\n')
    coletores = {"docker": coletor_falso([]), "http": coletor_falso([])}

    codigo = collect.main([*ambiente(tmp_path, projeto=projeto), "--confirmar", "cluster"],
                          coletores=coletores)

    assert codigo == 2
    assert "2026-09-31" in capsys.readouterr().err
    assert not (tmp_path / "saida" / "report.json").exists()


def test_sem_infra_explicito_os_alvos_vem_da_pasta_do_relatorio(tmp_path, monkeypatch):
    """Sem `--infra`, os alvos são os do PROJETO: `<pasta do relatório>/alvos.toml`."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs" / "infra").mkdir(parents=True)
    (tmp_path / "docs" / "infra" / "alvos.toml").write_text(
        '[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://127.0.0.1:1/x"\n', encoding="utf-8")
    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n', encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = ["site"]\n', encoding="utf-8")
    visitados = []

    codigo = collect.main(["--padrao", str(tmp_path / "default.toml"),
                           "--projeto", str(tmp_path / ".sw-infra-audit.toml"),
                           "--out", str(tmp_path / "docs/infra/2026-09-19_1000"),
                           "--at", "2026-09-19T10:00:00Z", "--confirmar", "site"],
                          coletores={"http": coletor_falso(visitados)})

    assert codigo == 0 and visitados == ["site"]


def test_auditar_recusa_alvos_em_pasta_que_o_git_versiona(tmp_path, monkeypatch, capsys):
    """Conexão dentro da árvore de um repo sem estar ignorada: para antes de coletar."""
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs" / "infra").mkdir(parents=True)
    (tmp_path / "docs" / "infra" / "alvos.toml").write_text(
        '[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://127.0.0.1:1/x"\n', encoding="utf-8")
    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n', encoding="utf-8")
    (tmp_path / ".sw-infra-audit.toml").write_text('alvos = ["site"]\n', encoding="utf-8")
    visitados = []

    codigo = collect.main(["--padrao", str(tmp_path / "default.toml"),
                           "--projeto", str(tmp_path / ".sw-infra-audit.toml"),
                           "--out", str(tmp_path / "docs/infra/2026-09-19_1000"),
                           "--at", "2026-09-19T10:00:00Z", "--confirmar", "site"],
                          coletores={"http": coletor_falso(visitados)})

    assert codigo == 2 and visitados == []
    assert ".gitignore" in capsys.readouterr().err


def test_achado_do_componente_e_promovido_para_o_alvo(tmp_path):
    """O relatório ordena, inventaria e compara histórico a partir de UMA lista — a do alvo.
    Achado que fica só no componente some dessas três coisas."""
    def coletor(alvo, contexto):
        return {"saude": "🟡",
                "componentes": [{"nome": "proxy", "papel": "entrada", "respostas": [],
                                 "analise": "",
                                 "achados": [{"regra": "SEC_PORT_EXPOSED", "objeto": "adminer",
                                              "severidade": "medium"}]}]}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"],
                 coletores={"docker": coletor, "http": coletor_falso([])})
    alvo = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert [a["regra"] for a in alvo["achados"]] == ["SEC_PORT_EXPOSED"]
    assert alvo["achados"][0]["componente"] == "proxy"
    assert alvo["achados"][0]["alvo"] == "cluster"
    assert alvo["componentes"][0]["achados"][0]["regra"] == "SEC_PORT_EXPOSED"


def test_componentes_invalidos_nao_derrubam_o_alvo(tmp_path):
    def coletor(alvo, contexto):
        return {"saude": "🟢", "componentes": "isto não é lista"}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"],
                 coletores={"docker": coletor, "http": coletor_falso([])})
    alvo = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert alvo["componentes"] == []
    assert any("componentes" in n["motivo"] for n in alvo["nao_coletado"])


def test_componente_malformado_nao_derruba_a_auditoria(tmp_path):
    """"Nada que o coletor devolva pode derrubar a auditoria dos outros alvos" — inclusive
    uma lista de componentes com lixo dentro."""
    def coletor(alvo, contexto):
        return {"saude": "🟢", "componentes": ["proxy", {"papel": "fila"}, 42]}

    codigo = collect.main([*ambiente(tmp_path), "--confirmar", "cluster"],
                          coletores={"docker": coletor, "http": coletor_falso([])})
    alvo = next(a for a in ler_relatorio(tmp_path)["alvos"] if a["nome"] == "cluster")

    assert codigo == 0
    assert alvo["componentes"] == []
    assert len([n for n in alvo["nao_coletado"] if "componente" in n["motivo"]]) == 3
