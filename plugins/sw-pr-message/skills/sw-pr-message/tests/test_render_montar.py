import json

import pytest

from render import montar

H1 = "a1b2c3d" + "1" * 33
H2 = "e4f5a6b" + "2" * 33


def fatos(provavel=False):
    return {"commits": [{"hash": H1, "assunto": "a"}, {"hash": H2, "assunto": "b"}],
            "hotfix": {"provavel": provavel, "sinais": []}}


def mud(**extra):
    base = {
        "idioma": "pt",
        "titulo": "feat(pagamentos): Integração com gateway",
        "resumo": "Permite cobrar por Pix 🚀 no checkout.",
        "secoes": {
            "interno": [{"texto": "Serviço de cobrança extraído", "commits": [H2]}],
            "novas": [{"texto": "Pagamento por Pix → QR Code ✓", "commits": [H1]}],
            "ajustes": [],
        },
        "como_testar": ["Criar um pedido", "Escolher Pix"],
    }
    base.update(extra)
    return base


def test_titulo_e_secoes_na_ordem_fixa_com_vazias_omitidas():
    texto = montar(fatos(), mud())

    assert texto.startswith("# Integração com gateway\n\n## Resumo\n\nPermite cobrar por Pix no checkout.\n")
    assert texto.index("## Novas funcionalidades") < texto.index("## Interno") < texto.index("## Como testar")
    assert "## Ajustes" not in texto
    assert "## Correções" not in texto


def test_itens_em_lista_e_passos_numerados():
    texto = montar(fatos(), mud())

    assert "- Pagamento por Pix → QR Code ✓\n" in texto
    assert "1. Criar um pedido\n2. Escolher Pix\n" in texto


def test_como_testar_vazio_some():
    assert "Como testar" not in montar(fatos(), mud(como_testar=[]))


def test_hash_nunca_aparece_no_texto():
    texto = montar(fatos(), mud())

    assert H1[:7] not in texto and H2[:7] not in texto


def test_rotulos_em_ingles():
    texto = montar(fatos(), mud(idioma="en"))

    assert "## Summary" in texto and "## New features" in texto
    assert "## Internal" in texto and "## How to test" in texto


def test_hotfix_fica_logo_depois_do_resumo_e_campo_null_vira_comentario():
    m = mud(hotfix={"causa": "Timeout de 5s no gateway", "impacto": None, "rollback": "Reverter o deploy"})

    texto = montar(fatos(provavel=True), m)

    assert texto.index("## Resumo") < texto.index("## Hotfix") < texto.index("## Novas funcionalidades")
    assert "**Causa:** Timeout de 5s no gateway\n" in texto
    assert "<!-- preencher: **Impacto:** -->\n" in texto
    assert "**Rollback:** Reverter o deploy\n" in texto


def test_hotfix_com_tres_null_fica_inteiro_dentro_de_um_comentario():
    m = mud(hotfix={"causa": None, "impacto": None, "rollback": None})

    texto = montar(fatos(provavel=True), m)

    abre = texto.index("<!-- preencher:")
    titulo = texto.index("## Hotfix")
    fecha = texto.index("-->", titulo)
    assert abre < titulo < fecha
    assert texto.count("## Hotfix") == 1


def test_comentario_de_lacuna_em_ingles():
    m = mud(idioma="en", hotfix={"causa": "x", "impacto": None, "rollback": "y"})

    assert "<!-- fill in: **Impact:** -->" in montar(fatos(provavel=True), m)


def test_sem_hotfix_quando_fatos_nao_indicam():
    assert "Hotfix" not in montar(fatos(provavel=False), mud())


def test_ff4_render_deterministico_byte_a_byte():
    f, m = fatos(provavel=True), mud(hotfix={"causa": "a", "impacto": None, "rollback": None})

    primeira = montar(f, m).encode("utf-8")
    segunda = montar(json.loads(json.dumps(f)), json.loads(json.dumps(m))).encode("utf-8")

    assert primeira == segunda
    assert primeira.endswith(b"\n") and not primeira.endswith(b"\n\n")


@pytest.mark.parametrize("idioma,titulos,campos", [
    ("pt", ["## Resumo", "## Hotfix", "## Novas funcionalidades", "## Ajustes", "## Correções",
            "## Removido", "## Segurança", "## Interno", "## Como testar"],
     ["**Causa:** c", "**Impacto:** i", "**Rollback:** r"]),
    ("en", ["## Summary", "## Hotfix", "## New features", "## Changes", "## Fixes",
            "## Removed", "## Security", "## Internal", "## How to test"],
     ["**Root cause:** c", "**Impact:** i", "**Rollback:** r"]),
])
def test_todas_as_secoes_saem_na_ordem_e_com_os_rotulos_exatos(idioma, titulos, campos):
    cheio = {c: [{"texto": f"item de {c}", "commits": [H1]}]
             for c in ("seguranca", "novas", "interno", "correcoes", "removido", "ajustes")}
    m = mud(idioma=idioma, secoes=cheio, hotfix={"causa": "c", "impacto": "i", "rollback": "r"})

    texto = montar(fatos(provavel=True), m)

    assert [l for l in texto.splitlines() if l.startswith("## ")] == titulos
    assert [l for l in texto.splitlines() if l.startswith("**")] == campos


def test_quebra_de_linha_do_agente_nao_cria_secao():
    m = mud(titulo="Tela\n## Falsa", resumo="Um\n## Falsa no resumo",
            secoes={"novas": [{"texto": "Tela\n## Seção falsa\n- item falso", "commits": [H1]}]},
            como_testar=["Abrir\n## Falsa no passo"],
            hotfix={"causa": "x\n## Falsa", "impacto": None, "rollback": None})

    texto = montar(fatos(provavel=True), m)

    assert [l for l in texto.splitlines() if l.startswith("## ")] == \
        ["## Resumo", "## Hotfix", "## Novas funcionalidades", "## Como testar"]
    assert texto.splitlines()[0] == "# Tela ## Falsa"


@pytest.mark.parametrize("resumo,escapado", [
    ("## Falso", "\\## Falso"), ("<!-- rascunho", "\\<!-- rascunho"), ("```js", "\\```js"),
])
def test_resumo_que_comeca_como_bloco_vira_paragrafo(resumo, escapado):
    linhas = montar(fatos(), mud(resumo=resumo)).splitlines()

    assert linhas[linhas.index("## Resumo") + 2] == escapado
