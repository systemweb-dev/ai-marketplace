# tests/test_regras.py
import json

import collect
from lib import perguntas, rules
from lib.coletores import http as coletor_http
from lib.regras import REGRAS, esperada, exigem_remediacao, severidade


def test_todo_produtor_declara_suas_regras_no_registro():
    """O registro é a fonte enumerável. Regra que nasce fora dele não ganha remediação —
    e é assim que um achado chega ao relatório sem dizer o que fazer."""
    assert rules.REGRAS_PRODUZIDAS <= set(REGRAS), sorted(rules.REGRAS_PRODUZIDAS - set(REGRAS))
    assert coletor_http.REGRAS_PRODUZIDAS <= set(REGRAS), \
        sorted(coletor_http.REGRAS_PRODUZIDAS - set(REGRAS))
    # o terceiro produtor: limiar declarado numa pergunta canônica
    assert perguntas.REGRAS_PRODUZIDAS <= set(REGRAS), \
        sorted(perguntas.REGRAS_PRODUZIDAS - set(REGRAS))


def test_o_registro_nao_guarda_regra_que_ninguem_produz():
    """`rule_meta` carregava OPS_SERVICE_DOWN, que nenhum produtor emite. Entrada morta em
    catálogo é pior que ausência: dá a impressão de cobertura que não existe."""
    produzidas = (rules.REGRAS_PRODUZIDAS | coletor_http.REGRAS_PRODUZIDAS
                  | perguntas.REGRAS_PRODUZIDAS)
    assert set(REGRAS) == produzidas, sorted(set(REGRAS) ^ produzidas)


def test_o_relatorio_nunca_traz_regra_fora_do_registro(tmp_path):
    """Prova pelo comportamento: coleta real contra um endereço morto, achados reais."""
    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "site"\ntipo = "http"\nurl = "http://127.0.0.1:1/x"\n', encoding="utf-8")
    (tmp_path / "config.toml").write_text('alvos = ["site"]\n', encoding="utf-8")

    collect.main(["--padrao", str(tmp_path / "default.toml"),
                  "--infra", str(tmp_path / "alvos.toml"),
                  "--projeto", str(tmp_path / "config.toml"),
                  "--out", str(tmp_path / "saida"), "--at", "2026-09-19T10:00:00Z",
                  "--confirmar", "site"], coletores={"http": coletor_http.coletar})
    relatorio = json.loads((tmp_path / "saida" / "report.json").read_text(encoding="utf-8"))

    regras = {a.get("regra") for alvo in relatorio["alvos"] for a in alvo["achados"]}
    assert regras <= set(REGRAS), sorted(regras - set(REGRAS))


def test_registro_descreve_severidade_origem_e_esperada():
    assert severidade("SEC_PORT_EXPOSED") == "medium"
    assert REGRAS["certificado_vencendo"]["origem"] == "coletor_http"
    assert esperada("SEC_DOCKER_SOCK_EXPECTED") is True
    assert esperada("OPS_JOB_COMPLETED") is True, "job concluído é o estado normal, não problema"
    assert esperada("SEC_PORT_EXPOSED") is False


def test_regra_esperada_nao_exige_remediacao():
    exigidas = exigem_remediacao()
    assert "SEC_DOCKER_SOCK_EXPECTED" not in exigidas and "OPS_JOB_COMPLETED" not in exigidas
    assert "SEC_PORT_EXPOSED" in exigidas and "http_fora_do_ar" in exigidas


def test_rule_meta_nao_descreve_regra_que_nao_existe():
    """Texto explicativo de uma regra que ninguém emite é cobertura de mentira: dá a
    impressão de que o relatório sabe explicar algo que nunca vai aparecer nele."""
    from lib.rule_meta import RULE_META
    orfas = sorted(set(RULE_META) - set(REGRAS))
    assert orfas == [], f"rule_meta descreve regra inexistente: {orfas}"


# ---------------------------------------------------------------- o registro não pode divergir
VOCABULARIO_V1 = {"crit": "critical", "critical": "critical", "high": "high",
                  "med": "medium", "medium": "medium", "low": "low", "info": "info"}


def _emitidas_por_rules():
    """Lê `rules.py` e devolve {id: (severidade, esperada)} como o produtor REALMENTE emite.

    Precisa de AST porque duas regras (`OPS_TLS_EXPIRED`, `OPS_DAEMON_UNREACHABLE`) saem por
    variável, não por literal na chamada — foi exatamente aí que um grep ingênuo se enganou.
    """
    import ast
    import pathlib

    arquivo = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "lib" / "rules.py"
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    emitidas = {}
    for funcao in [n for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef)]:
        atual = {}                      # último valor atribuído a cada variável local
        for no in ast.walk(funcao):
            if isinstance(no, ast.Assign) and isinstance(no.value, ast.Constant):
                for alvo in no.targets:
                    if isinstance(alvo, ast.Name):
                        atual[alvo.id] = no.value.value
            if not (isinstance(no, ast.Call) and getattr(no.func, "id", "") == "_f"):
                continue
            primeiro = no.args[0]
            rid = (primeiro.value if isinstance(primeiro, ast.Constant)
                   else atual.get(getattr(primeiro, "id", "")))
            sev = no.args[1].value if isinstance(no.args[1], ast.Constant) else None
            esperado = any(k.arg == "expected" and getattr(k.value, "value", False)
                           for k in no.keywords)
            if rid and sev:
                emitidas[rid] = (VOCABULARIO_V1[sev], esperado or emitidas.get(rid, (0, False))[1])
    return emitidas


def _emitidas_por_http():
    """Os achados do coletor http são dicionários literais com `regra` e `severidade`."""
    import ast
    import pathlib

    arquivo = (pathlib.Path(__file__).resolve().parents[1] / "scripts" / "lib" / "coletores"
               / "http.py")
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    emitidas = {}
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Dict):
            continue
        chaves = {k.value: v for k, v in zip(no.keys, no.values)
                  if isinstance(k, ast.Constant)}
        if "regra" not in chaves or "severidade" not in chaves:
            continue
        regra, sev = chaves["regra"], chaves["severidade"]
        if isinstance(regra, ast.Constant) and isinstance(sev, ast.Constant):
            emitidas[regra.value] = (VOCABULARIO_V1[sev.value], False)
        elif isinstance(regra, ast.Constant):     # severidade condicional (crítico ou alto)
            emitidas.setdefault(regra.value, (None, False))
    return emitidas


def test_severidade_do_registro_bate_com_a_que_o_produtor_emite():
    """Amostrar uma regra não prova nada: o registro existe para NÃO divergir do produtor.
    Divergência aqui é achado saindo com a gravidade errada no relatório."""
    divergentes = []
    for regra, (sev, _) in {**_emitidas_por_rules(), **_emitidas_por_http()}.items():
        if sev is None:                  # severidade calculada em tempo de execução
            continue
        if REGRAS[regra]["severidade_padrao"] != sev:
            divergentes.append(f"{regra}: registro={REGRAS[regra]['severidade_padrao']} "
                               f"produtor={sev}")
    assert divergentes == [], divergentes


def test_marca_esperada_bate_com_o_expected_do_produtor():
    """`esperada` tira a regra de `exigem_remediacao()` e da nota. Marcar errado faz um
    achado de verdade sumir do 'como resolver' sem nenhum teste piscar."""
    divergentes = [f"{regra}: registro={REGRAS[regra]['esperada']} produtor={esperado}"
                   for regra, (_, esperado) in _emitidas_por_rules().items()
                   if REGRAS[regra]["esperada"] != esperado]
    assert divergentes == [], divergentes


def test_origem_declarada_bate_com_quem_emite():
    for regra in rules.REGRAS_PRODUZIDAS:
        assert REGRAS[regra]["origem"] == "rules", regra
    for regra in coletor_http.REGRAS_PRODUZIDAS:
        assert REGRAS[regra]["origem"] == "coletor_http", regra
