# tests/test_sinais.py
from pathlib import Path

from lib import sinais
from projeto import PHPUNIT_RUIM, PYTEST_BOM, PYTEST_RUIM, VITEST_RUIM


def regras(achados):
    return sorted({a["regra"] for a in achados})


def test_teste_bom_nao_gera_sinal(tmp_path):
    achados = sinais.varrer(Path("tests/unit/test_calculadora.py"), PYTEST_BOM, "unit")

    assert achados == []


def test_python_ruim_gera_os_sinais_esperados():
    achados = sinais.varrer(Path("tests/unit/test_problemas.py"), PYTEST_RUIM, "unit")

    assert regras(achados) == ["aleatorio_sem_semente", "espera_fixa", "marcado_para_pular",
                               "relogio_real", "sem_assercao_aparente"]


def test_cada_sinal_aponta_o_teste_e_a_linha():
    achados = sinais.varrer(Path("tests/unit/test_problemas.py"), PYTEST_RUIM, "unit")
    pulado = next(a for a in achados if a["regra"] == "marcado_para_pular")

    assert pulado["teste"] == "test_desligado"
    assert PYTEST_RUIM.splitlines()[pulado["linha"] - 1].strip().startswith("@pytest.mark.skip")


def test_js_pega_skip_espera_relogio_e_nome_repetido():
    achados = sinais.varrer(Path("tests/unit/carrinho.test.ts"), VITEST_RUIM, "unit")

    assert regras(achados) == ["espera_fixa", "marcado_para_pular", "nome_duplicado",
                               "relogio_real", "sem_assercao_aparente"]
    duplicado = next(a for a in achados if a["regra"] == "nome_duplicado")
    assert duplicado["teste"] == "nome repetido"


def test_php_pega_skip_sem_assercao_e_rede():
    achados = sinais.varrer(Path("tests/Unit/CarrinhoTest.php"), PHPUNIT_RUIM, "unit")

    assert regras(achados) == ["marcado_para_pular", "rede_em_unit", "sem_assercao_aparente"]


def test_rede_so_vira_sinal_em_suite_unitaria():
    achados = sinais.varrer(Path("tests/Integration/CarrinhoTest.php"), PHPUNIT_RUIM, "integracao")

    assert "rede_em_unit" not in regras(achados)


def test_relogio_congelado_no_arquivo_desliga_o_sinal():
    texto = "from freezegun import freeze_time\n\n\n@freeze_time('2026-01-01')\n" \
            "def test_x():\n    assert datetime.now().year == 2026\n"

    achados = sinais.varrer(Path("tests/unit/test_x.py"), texto, "unit")

    assert regras(achados) == []


def test_aleatorio_com_semente_nao_vira_sinal():
    texto = "import random\n\n\ndef test_x():\n    random.seed(7)\n    assert random.random() < 1\n"

    assert sinais.varrer(Path("tests/unit/test_x.py"), texto, "unit") == []


def test_helper_de_assercao_ainda_gera_sinal_mas_de_confianca_media():
    texto = "def test_x():\n    conferir_total(10)\n"

    achados = sinais.varrer(Path("tests/unit/test_x.py"), texto, "unit")

    assert [a["regra"] for a in achados] == ["sem_assercao_aparente"]
    assert sinais.REGRAS["sem_assercao_aparente"][2] == "media", \
        "helper de asserção dá falso positivo; alta confiança só com plugin de lint"


def test_toda_regra_declara_descricao_dimensao_e_confianca():
    dimensoes = {"confiabilidade", "isolamento", "cobertura", "legibilidade", "velocidade"}

    for identificador, (descricao, dimensao, confianca) in sinais.REGRAS.items():
        assert identificador.islower() and " " not in identificador
        assert descricao and dimensao in dimensoes and confianca in {"alta", "media", "baixa"}


def test_sleep_em_comentario_ou_string_nao_vira_sinal():
    texto = ("def test_x():\n"
             "    # aqui tinha um time.sleep(2) que foi removido\n"
             "    mensagem = 'evite sleep( no teste'\n"
             "    assert mensagem\n")

    assert sinais.varrer(Path("tests/unit/test_x.py"), texto, "unit") == []


def test_only_dentro_de_texto_nao_desliga_o_teste():
    texto = "it('explica o .only( do vitest', () => { expect(1).toBe(1); });\n"

    assert sinais.varrer(Path("tests/unit/a.test.ts"), texto, "unit") == []


def test_rede_mockada_no_arquivo_nao_vira_sinal():
    texto = ("import { vi, it, expect } from 'vitest';\n"
             "vi.mock('./api');\n\n"
             "it('busca itens', async () => {\n"
             "  const r = await fetch('/itens');\n"
             "  expect(r).toBeTruthy();\n"
             "});\n")

    assert sinais.varrer(Path("tests/unit/a.test.ts"), texto, "unit") == []


def test_reconhece_teste_de_go_ruby_e_anotacao():
    go = "func TestSoma(t *testing.T) {\n    t.Error(\"x\")\n}\n"
    ruby = "it 'soma dois numeros' do\n  expect(somar(2, 2)).to eq 4\nend\n"
    java = "@Test\npublic void somaDoisNumeros() {\n    assertEquals(4, somar(2, 2));\n}\n"

    assert [b[0] for b in sinais.blocos(go)] == ["TestSoma"]
    assert [b[0] for b in sinais.blocos(ruby)] == ["soma dois numeros"]
    assert len(sinais.blocos(java)) == 1


def test_catalogo_de_regras_nao_esta_vazio():
    assert len(sinais.REGRAS) >= 7


def test_espera_de_atraso_zero_nao_e_espera_fixa():
    """`setTimeout(r, 0)` é o idioma para drenar promessas pendentes, não uma espera."""
    drenar = ("it('salva', async () => {\n"
              "  await new Promise(r => setTimeout(r, 0));\n"
              "  expect(salvo).toBe(true);\n"
              "});\n")
    esperar = ("it('salva', async () => {\n"
               "  await new Promise(r => setTimeout(r, 500));\n"
               "  expect(salvo).toBe(true);\n"
               "});\n")

    assert sinais.varrer(Path("tests/unit/a.test.ts"), drenar, "unit") == []
    assert [a["regra"] for a in sinais.varrer(Path("tests/unit/a.test.ts"), esperar, "unit")] == \
        ["espera_fixa"]
