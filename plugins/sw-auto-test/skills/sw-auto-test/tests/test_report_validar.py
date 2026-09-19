# tests/test_report_validar.py
import json

import pytest

from report import validar

FATOS = {
    "versao": 1,
    "repo": {"toplevel": "/x", "branch": "master", "head": "a" * 40},
    "escopo": {"tipo": "repo", "raiz": "."},
    "stacks": [{"linguagem": "py", "runner": "pytest", "nativo": True, "config": "pyproject.toml"}],
    "inventario": {"arquivos": 1, "testes": 2, "por_suite": {"unit": 2},
                   "lista": [{"caminho": "tests/unit/test_a.py", "testes": 2, "suite": "unit"}]},
    "execucao": {"rodou": False, "verde": None, "timeout": False, "passou": 0, "falhou": 0,
                 "pulado": 0, "duracao_faixa": None, "lentos": []},
    "cobertura": {"disponivel": False, "ferramenta": None, "por_arquivo": []},
    "sinais": [{"regra": "marcado_para_pular", "caminho": "tests/unit/test_a.py", "linha": 3,
                "evidencia": "@pytest.mark.skip", "teste": "test_x"}],
    "suspeitos": ["tests/unit/test_a.py"],
}


def achado(**extra):
    base = {"regra": "teste_desligado", "dimensao": "confiabilidade", "confianca": "alta",
            "caminho": "tests/unit/test_a.py", "linha": 3, "problema": "teste desligado há meses",
            "correcao": "reativar ou apagar", "sinal": "marcado_para_pular"}
    base.update(extra)
    return base


def test_achados_validos_passam():
    assert validar(FATOS, {"versao": 1, "achados": [achado()], "nao_e_problema": []}) == []


def test_lista_todos_os_problemas_de_uma_vez():
    """Cada achado carrega UM defeito, em linha própria: senão a regra de repetição soma junto."""
    ruins = {"versao": 1, "achados": [
        achado(dimensao="velocidade_maxima", linha=1),
        achado(confianca="altissima", linha=2),
        achado(caminho="tests/unit/nao-existe.py", linha=3, confianca="media", sinal=None),
        achado(problema="   ", linha=4, confianca="media", sinal=None),
        achado(correcao="", linha=5, confianca="media", sinal=None),
    ], "nao_e_problema": []}

    problemas = validar(FATOS, ruins)

    assert len(problemas) == 5, problemas
    assert any("dimensao" in p for p in problemas) and any("confianca" in p for p in problemas)
    assert any("nao-existe.py" in p for p in problemas)
    assert any("problema vazio" in p for p in problemas)
    assert any("correcao vazia" in p for p in problemas)


def test_confianca_alta_exige_sinal_do_script():
    sem_lastro = {"versao": 1, "achados": [achado(sinal="assercao_tautologica")], "nao_e_problema": []}

    problemas = validar(FATOS, sem_lastro)

    assert any("sem lastro" in p for p in problemas)


def test_confianca_media_nao_exige_sinal():
    julgado = {"versao": 1, "achados": [achado(confianca="media", sinal=None)], "nao_e_problema": []}

    assert validar(FATOS, julgado) == []


def test_achado_repetido_e_recusado():
    repetido = {"versao": 1, "achados": [achado(), achado()], "nao_e_problema": []}

    assert any("repetido" in p for p in validar(FATOS, repetido))


def test_linha_fora_do_arquivo_e_recusada(tmp_path):
    fatos = dict(FATOS, repo=dict(FATOS["repo"], toplevel=str(tmp_path)))
    (tmp_path / "tests/unit").mkdir(parents=True)
    (tmp_path / "tests/unit/test_a.py").write_text("um\ndois\n", encoding="utf-8")

    problemas = validar(fatos, {"versao": 1, "achados": [achado(linha=99, sinal=None,
                                                               confianca="media")],
                                "nao_e_problema": []})

    assert any("linha 99" in p for p in problemas)


def test_tipos_errados_viram_problema_e_nao_excecao():
    torto = {"versao": 1, "achados": "isto devia ser lista", "nao_e_problema": {}}

    problemas = validar(FATOS, torto)

    assert problemas and all(isinstance(p, str) for p in problemas)


def test_nao_e_problema_precisa_de_caminho_e_motivo():
    torto = {"versao": 1, "achados": [], "nao_e_problema": [{"caminho": "tests/unit/test_a.py"}]}

    assert any("motivo" in p for p in validar(FATOS, torto))


def test_regra_precisa_ser_texto_simples():
    injetado = {"versao": 1, "achados": [achado(regra="x\n\n## Seção falsa\n\n| a | b |")],
                "nao_e_problema": []}

    assert any("regra" in p for p in validar(FATOS, injetado))


def test_caminho_ou_linha_de_tipo_errado_viram_problema_e_nao_excecao():
    torto = {"versao": 1, "achados": [achado(caminho=["a"], linha=[3], confianca="media", sinal=None)],
             "nao_e_problema": []}

    problemas = validar(FATOS, torto)

    assert problemas and all(isinstance(p, str) for p in problemas)


def test_linha_booleana_nao_passa_por_inteiro():
    torto = {"versao": 1, "achados": [achado(linha=True, confianca="media", sinal=None)],
             "nao_e_problema": []}

    assert any("linha" in p for p in validar(FATOS, torto))


def test_ultima_linha_do_arquivo_e_valida_e_a_seguinte_nao(tmp_path):
    fatos = dict(FATOS, repo=dict(FATOS["repo"], toplevel=str(tmp_path)))
    (tmp_path / "tests/unit").mkdir(parents=True)
    (tmp_path / "tests/unit/test_a.py").write_text("um\ndois\n", encoding="utf-8")

    def com_linha(numero):
        return validar(fatos, {"versao": 1, "achados": [achado(linha=numero, confianca="media",
                                                              sinal=None)], "nao_e_problema": []})

    assert com_linha(2) == []
    assert any("linha 3" in p for p in com_linha(3)), "o arquivo tem 2 linhas"


def test_nao_e_problema_com_caminho_fora_do_inventario_e_recusado():
    torto = {"versao": 1, "achados": [],
             "nao_e_problema": [{"caminho": "tests/unit/nao-existe.py", "motivo": "convenção"}]}

    assert any("nao-existe.py" in p for p in validar(FATOS, torto))


def test_item_nulo_dentro_de_achados_vira_problema():
    problemas = validar(FATOS, {"versao": 1, "achados": [None, achado()], "nao_e_problema": []})

    assert any("objeto" in p for p in problemas)
