import pytest

from render import limpar, limpar_titulo, validar

H1 = "abcdef1" + "1" * 33
H2 = "abcdef1" + "2" * 33
H3 = "0123456" + "3" * 33


def fatos(*hashes, provavel=False):
    return {
        "commits": [{"hash": h, "assunto": f"commit {h[:7]}"} for h in hashes],
        "hotfix": {"provavel": provavel, "sinais": []},
    }


def mud(**extra):
    base = {
        "idioma": "pt",
        "titulo": "Tela de login",
        "resumo": "Permite entrar no sistema.",
        "secoes": {"novas": [{"texto": "Tela de login", "commits": [H3[:7]]}]},
        "como_testar": [],
    }
    base.update(extra)
    return base


def test_mudancas_completo_nao_tem_problema():
    assert validar(fatos(H3), mud()) == []


def test_lista_todos_os_problemas_de_uma_vez():
    ruim = {
        "idioma": "xx",
        "titulo": "",
        "resumo": "",
        "secoes": {"novidades": [], "novas": [{"texto": "algo", "commits": []}]},
    }

    problemas = validar(fatos(H3, provavel=True), ruim)

    texto = "\n".join(problemas)
    for esperado in ("idioma inválido", "titulo vazio", "resumo vazio", "seção desconhecida",
                     "item sem commits", "commit esquecido", "hotfix obrigatório"):
        assert esperado in texto, esperado
    assert len(problemas) == 7


def test_commit_esquecido_e_apontado():
    problemas = validar(fatos(H3, H1), mud())

    assert problemas == [f"commit esquecido: {H1[:7]} commit {H1[:7]}"]


def test_hash_curto_desconhecido_e_ambiguo_sao_recusados():
    m = mud(secoes={"novas": [{"texto": "x", "commits": ["abc", "fffffff", "abcdef1"]}]})

    problemas = "\n".join(validar(fatos(H1, H2), m))

    assert "hash curto: 'abc'" in problemas
    assert "hash desconhecido: 'fffffff'" in problemas
    assert "hash ambiguo: 'abcdef1'" in problemas


def test_prefixo_longo_o_bastante_resolve_sem_ambiguidade():
    m = mud(secoes={"novas": [{"texto": "a", "commits": ["abcdef11"]},
                              {"texto": "b", "commits": ["abcdef12"]}]})

    assert validar(fatos(H1, H2), m) == []


def test_sem_item_cobre_commit_sem_efeito_liquido():
    m = mud(sem_item=[{"hash": H1[:7], "motivo": "desfeito pelo commit seguinte"}])

    assert validar(fatos(H3, H1), m) == []


def test_commit_num_item_e_em_sem_item_ao_mesmo_tempo_e_recusado():
    m = mud(sem_item=[{"hash": H3[:7], "motivo": "nada"}])

    assert validar(fatos(H3), m) == [f"commit {H3[:7]} está num item e em sem_item"]


def test_mesmo_commit_em_dois_itens_e_permitido():
    m = mud(secoes={"novas": [{"texto": "a", "commits": [H3]}],
                    "ajustes": [{"texto": "b", "commits": [H3]}]})

    assert validar(fatos(H3), m) == []


def test_titulo_que_so_tinha_prefixo_e_recusado():
    assert validar(fatos(H3), mud(titulo="feat(auth): ")) == ["titulo vazio depois de remover o prefixo"]


def test_hotfix_inconsistente_nos_dois_sentidos():
    obrigatorio = validar(fatos(H3, provavel=True), mud())
    proibido = validar(fatos(H3, provavel=False), mud(hotfix={"causa": "x", "impacto": None, "rollback": None}))

    assert obrigatorio == ["hotfix obrigatório: fatos indicam hotfix (use null nos campos sem evidência)"]
    assert proibido == ["hotfix não permitido: fatos não indicam hotfix"]


def test_hotfix_com_todos_os_campos_null_e_aceito_quando_provavel():
    m = mud(hotfix={"causa": None, "impacto": None, "rollback": None})

    assert validar(fatos(H3, provavel=True), m) == []


def test_limpar_tira_emoji_e_preserva_marcas_tipograficas():
    assert limpar("Novo ✨ fluxo 🚀 → pronto ✓ ✔ • – — ⚠️") == "Novo fluxo → pronto ✓ ✔ • – —"


def test_limpar_titulo_tira_so_prefixo_conventional_ou_colchete():
    assert limpar_titulo("feat(auth)!: Login com Google") == "Login com Google"
    assert limpar_titulo("FIX: Corrige checkout") == "Corrige checkout"
    assert limpar_titulo("[Feature] Painel novo") == "Painel novo"
    assert limpar_titulo("✨ feat: Painel") == "Painel"
    assert limpar_titulo("Checkout: novo fluxo de pagamento") == "Checkout: novo fluxo de pagamento"


@pytest.mark.parametrize("extra,provavel,esperado", [
    ({"secoes": {"novas": ["texto solto"]}}, False, "novas[1] deve ser um objeto"),
    ({"secoes": {"ajustes": "x"}}, False, "secoes.ajustes deve ser uma lista"),
    ({"secoes": {"novas": [{"texto": "a", "commits": "0123456"}]}}, False, "novas[1]: commits deve ser uma lista"),
    ({"secoes": {"novas": [{"texto": {"a": "b"}, "commits": [H3]}]}}, False, "novas[1]: texto deve ser texto"),
    ({"sem_item": "x"}, False, "sem_item deve ser uma lista"),
    ({"sem_item": ["0123456"]}, False, "sem_item[1] deve ser um objeto"),
    ({"como_testar": "Abrir a tela"}, False, "como_testar deve ser uma lista de textos"),
    ({"como_testar": [1, 2]}, False, "como_testar deve ser uma lista de textos"),
    ({"hotfix": "causa X"}, True, "hotfix deve ser um objeto"),
    ({"hotfix": {"causa": 1, "impacto": None, "rollback": None}}, True, "hotfix.causa deve ser texto ou null"),
    ({"titulo": 42}, False, "titulo deve ser texto"),
    ({"resumo": {"a": 1}}, False, "resumo deve ser texto"),
])
def test_tipo_errado_vira_problema_listado_sem_excecao(extra, provavel, esperado):
    problemas = validar(fatos(H3, provavel=provavel), mud(**extra))

    assert esperado in "\n".join(problemas)


def test_commits_em_texto_nao_gera_um_problema_por_caractere():
    m = mud(secoes={"novas": [{"texto": "a", "commits": "0123456"}]})

    assert "hash curto" not in "\n".join(validar(fatos(H3), m))


def test_item_com_texto_vazio_e_recusado():
    m = mud(secoes={"novas": [{"texto": "   ", "commits": [H3]}]})

    assert validar(fatos(H3), m) == ["novas[1]: texto vazio"]


def test_sem_item_com_motivo_vazio_e_recusado():
    m = mud(sem_item=[{"hash": H1[:7], "motivo": ""}])

    assert validar(fatos(H3, H1), m) == ["sem_item[1]: motivo vazio"]


def test_hash_em_maiusculas_resolve():
    m = mud(secoes={"novas": [{"texto": "x", "commits": ["ABCDEF1"]}]})

    assert validar(fatos(H1), m) == []


def test_limpar_junta_quebras_de_linha_e_ignora_nao_texto():
    assert limpar("Tela\n## Falsa\n\n- item") == "Tela ## Falsa - item"
    assert limpar(42) == "" and limpar(None) == ""


def test_limpar_remove_emoji_composto_e_de_apresentacao():
    familia = chr(0x1F468) + chr(0x200D) + chr(0x1F469) + chr(0x200D) + chr(0x1F467)
    keycap = "1" + chr(0xFE0F) + chr(0x20E3)
    outros = "".join(map(chr, (0x2B50, 0x23F3, 0x270A, 0x231B)))

    assert limpar(f"família {familia} passo {keycap} ok {outros} fim") == "família passo 1 ok fim"
