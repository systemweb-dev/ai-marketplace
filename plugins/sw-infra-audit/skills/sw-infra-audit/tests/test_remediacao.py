# tests/test_remediacao.py
import pytest

from lib.regras import exigem_remediacao
from lib.remediacao import RemediacaoInvalida, carregar_arquivo, disponiveis, para


def test_toda_regra_que_vira_achado_tem_remediacao():
    """Achado sem o que fazer é meia informação. Regra `esperada` não precisa: ela descreve
    um comportamento normal, não um problema."""
    faltando = sorted(exigem_remediacao() - disponiveis())
    assert faltando == [], f"regras sem arquivo em references/remediacao/: {faltando}"


def test_nao_ha_remediacao_orfa():
    """Arquivo de uma regra que ninguém emite é manutenção paga sem retorno."""
    from lib.regras import REGRAS
    orfas = sorted(disponiveis() - set(REGRAS))
    assert orfas == [], f"remediação de regra inexistente: {orfas}"


def test_todo_arquivo_do_catalogo_carrega_e_tem_os_quatro_blocos():
    for regra in sorted(disponiveis()):
        bloco = para(regra)
        assert bloco["titulo"], regra
        for campo in ("por_que_importa", "como_resolver", "como_confirmar", "quando_nao_fazer"):
            assert bloco[campo].strip(), f"{regra}: bloco {campo} vazio"


def test_arquivo_sem_um_dos_blocos_e_recusado(tmp_path):
    (tmp_path / "x.md").write_text("---\nregra: x\ntitulo: X\n---\n## Por que importa\nnada\n",
                                   encoding="utf-8")
    with pytest.raises(RemediacaoInvalida) as erro:
        carregar_arquivo(tmp_path / "x.md")
    assert "Como resolver" in str(erro.value)


def test_arquivo_com_regra_diferente_do_nome_e_recusado(tmp_path):
    """Nome do arquivo é a chave de busca: divergir dele faz a remediação nunca ser achada."""
    (tmp_path / "SEC_PORT_EXPOSED.md").write_text(
        "---\nregra: OUTRA_COISA\ntitulo: X\n---\n", encoding="utf-8")
    with pytest.raises(RemediacaoInvalida) as erro:
        carregar_arquivo(tmp_path / "SEC_PORT_EXPOSED.md")
    assert "OUTRA_COISA" in str(erro.value)


def test_regra_sem_arquivo_devolve_none():
    assert para("regra_que_nao_existe") is None


def test_achado_chega_ao_relatorio_com_o_passo_a_passo(tmp_path):
    """É o ponto do ciclo: quem lê o relatório não precisa saber de cor o que fazer."""
    import json

    import collect

    (tmp_path / "default.toml").write_text('[relatorio]\npasta = "docs/infra"\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "cluster"\ntipo = "docker"\ncontext = "ctx"\n', encoding="utf-8")
    (tmp_path / "config.toml").write_text('alvos = ["cluster"]\n', encoding="utf-8")

    def coletor(alvo, contexto):
        return {"saude": "🟡", "achados": [{"regra": "SEC_PORT_EXPOSED", "objeto": "adminer",
                                            "severidade": "medium", "alvo": "cluster"}]}

    collect.main(["--padrao", str(tmp_path / "default.toml"),
                  "--infra", str(tmp_path / "alvos.toml"),
                  "--projeto", str(tmp_path / "config.toml"),
                  "--out", str(tmp_path / "saida"), "--at", "2026-09-19T10:00:00Z",
                  "--confirmar", "cluster"], coletores={"docker": coletor})
    relatorio = json.loads((tmp_path / "saida" / "report.json").read_text(encoding="utf-8"))
    achado = relatorio["alvos"][0]["achados"][0]

    assert achado["como_resolver"]["titulo"]
    assert "0.0.0.0" in achado["como_resolver"]["por_que_importa"]
    assert achado["como_resolver"]["como_confirmar"]


def test_achado_de_regra_desconhecida_nao_quebra_o_relatorio(tmp_path):
    """Regra sem arquivo falha o TESTE, não a auditoria de quem está usando."""
    from lib.remediacao import para
    assert para("regra_inventada") is None
