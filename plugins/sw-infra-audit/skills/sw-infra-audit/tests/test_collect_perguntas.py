# tests/test_collect_perguntas.py
import json

import collect


def ambiente(tmp_path):
    (tmp_path / "default.toml").write_text(
        '[relatorio]\npasta = "docs/infra"\n[limites]\ntimeout_por_comando = 5\n'
        'orcamento_por_alvo = 60\n[insights]\njanela = "24h"\n', encoding="utf-8")
    (tmp_path / "alvos.toml").write_text(
        '[[alvo]]\nnome = "cluster"\ntipo = "docker"\ncontext = "ctx"\n', encoding="utf-8")
    (tmp_path / "config.toml").write_text('alvos = ["cluster"]\n', encoding="utf-8")
    return ["--padrao", str(tmp_path / "default.toml"), "--infra", str(tmp_path / "alvos.toml"),
            "--projeto", str(tmp_path / "config.toml"), "--out", str(tmp_path / "saida"),
            "--at", "2026-09-19T10:00:00Z"]


def ler(tmp_path):
    return json.loads((tmp_path / "saida" / "report.json").read_text(encoding="utf-8"))


def coletor_com_componente(nome="proxy", papel="entrada", **extras):
    def coletar(alvo, contexto):
        return {"saude": "🟢", "componentes": [dict({"nome": nome, "papel": papel}, **extras)]}
    return coletar


class AdaptadorFalso:
    ID = "falso"
    RESPOSTAS = {}
    VISTAS = []

    @classmethod
    def perguntar(cls, pergunta, componente, contexto):
        cls.VISTAS.append((pergunta, contexto.get("timeout"), contexto.get("janela")))
        if pergunta in cls.RESPOSTAS:
            return dict(cls.RESPOSTAS[pergunta], pergunta=pergunta)
        return {"pergunta": pergunta, "sem_dados": True, "motivo": "não sei responder"}


def test_cada_componente_responde_as_perguntas_do_seu_papel(tmp_path):
    AdaptadorFalso.RESPOSTAS = {"entrada.volume_na_janela": {"fonte": "falso:x", "valor": 12480}}
    AdaptadorFalso.VISTAS = []

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"],
                 coletores={"docker": coletor_com_componente()}, adaptadores=[AdaptadorFalso])
    componente = ler(tmp_path)["alvos"][0]["componentes"][0]

    assert [r["pergunta"] for r in componente["respostas"]] == [
        "entrada.volume_na_janela", "entrada.distribuicao_de_status", "entrada.latencia"]
    assert componente["respostas"][0]["valor"] == 12480
    assert componente["respostas"][0]["fonte"] == "falso:x"
    assert componente["respostas"][1]["motivo"] == "não sei responder"


def test_papel_sem_pergunta_nao_gera_ruido(tmp_path):
    """`storage` ainda não tem pergunta: o componente aparece no inventário sem uma lista de
    `sem dados` inventada."""
    AdaptadorFalso.RESPOSTAS = {}
    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"],
                 coletores={"docker": coletor_com_componente(papel="storage")},
                 adaptadores=[AdaptadorFalso])
    assert ler(tmp_path)["alvos"][0]["componentes"][0]["respostas"] == []


def test_a_janela_configurada_chega_ao_adaptador(tmp_path):
    AdaptadorFalso.RESPOSTAS = {}
    AdaptadorFalso.VISTAS = []
    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"],
                 coletores={"docker": coletor_com_componente()}, adaptadores=[AdaptadorFalso])
    assert {janela for _, _, janela in AdaptadorFalso.VISTAS} == {"24h"}


def test_adaptador_que_estoura_nao_derruba_o_alvo(tmp_path):
    """O `except Exception` de coletar_alvo retorna cedo e apagaria o inventário inteiro por
    causa de UMA pergunta. O contorno é da pergunta, não do alvo."""
    class Quebrado:
        ID = "quebrado"

        @staticmethod
        def perguntar(pergunta, componente, contexto):
            raise RuntimeError("bug do adaptador")

    codigo = collect.main([*ambiente(tmp_path), "--confirmar", "cluster"],
                          coletores={"docker": coletor_com_componente()}, adaptadores=[Quebrado])
    alvo = ler(tmp_path)["alvos"][0]

    assert codigo == 0
    assert alvo["saude"] == "🟢", "o alvo não pode virar erro por causa de uma pergunta"
    assert all(r["erro_interno"] for r in alvo["componentes"][0]["respostas"])
    assert "bug do adaptador" in alvo["componentes"][0]["respostas"][0]["motivo"]


def test_o_primeiro_adaptador_que_sabe_responder_vence(tmp_path):
    class Generico:
        ID = "generico"

        @staticmethod
        def perguntar(pergunta, componente, contexto):
            return {"pergunta": pergunta, "fonte": "generico", "valor": 1}

    class Especifico:
        ID = "especifico"

        @staticmethod
        def perguntar(pergunta, componente, contexto):
            if pergunta == "entrada.volume_na_janela":
                return {"pergunta": pergunta, "fonte": "especifico", "valor": 99}
            return {"pergunta": pergunta, "sem_dados": True, "motivo": "não é comigo"}

    collect.main([*ambiente(tmp_path), "--confirmar", "cluster"],
                 coletores={"docker": coletor_com_componente()},
                 adaptadores=[Especifico, Generico])
    respostas = {r["pergunta"]: r for r in ler(tmp_path)["alvos"][0]["componentes"][0]["respostas"]}

    assert respostas["entrada.volume_na_janela"]["fonte"] == "especifico"
    assert respostas["entrada.latencia"]["fonte"] == "generico", \
        "quem sabe menos responde o que o mais específico não soube"


def test_orcamento_esgotado_corta_as_perguntas_seguintes(tmp_path):
    """Fonte lenta atrasa um alvo, não a auditoria — e o relatório diz que foi o orçamento."""
    class Lento:
        ID = "lento"

        @staticmethod
        def perguntar(pergunta, componente, contexto):
            return {"pergunta": pergunta, "fonte": "lento", "valor": 1}

    args = [a if a != "60" else "0" for a in ambiente(tmp_path)]
    (tmp_path / "default.toml").write_text(
        '[relatorio]\npasta = "docs/infra"\n[limites]\ntimeout_por_comando = 5\n'
        'orcamento_por_alvo = 0\n', encoding="utf-8")

    collect.main([*args, "--confirmar", "cluster"],
                 coletores={"docker": coletor_com_componente()}, adaptadores=[Lento])
    respostas = ler(tmp_path)["alvos"][0]["componentes"][0]["respostas"]

    assert all(r.get("sem_dados") for r in respostas)
    assert all("orçamento" in r["motivo"] for r in respostas)
