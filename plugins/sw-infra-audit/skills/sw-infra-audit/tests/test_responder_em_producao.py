# tests/test_responder_em_producao.py
"""O `responder` como o `main` o usa — não como os testes gostariam que fosse.

A revisão do batch 5 achou quatro coisas que só aparecem no caminho de produção:
- o `responder` copia o contexto a cada pergunta, então o cache de identificação caía na cópia
  e morria com ela: 3 perguntas, 3 identificações;
- o `main` nunca punha o nome do alvo no contexto, e a credencial "amarrada a (alvo, host,
  porta)" virava (None, host, porta) — o teste que provava a amarração injetava o alvo à mão;
- um adaptador que ESTOURA (`erro_interno`) contava como resposta e fazia `break`: o próximo
  adaptador nunca era consultado;
- o timeout de comando (20 s) era usado para HTTP, onde o configurado é 8 s.
"""
import collect
from lib.orcamento import Prazo


class Contador:
    """Adaptador falso que registra o contexto que recebe e usa o cache compartilhado."""
    ID = "contador"

    def __init__(self):
        self.contextos = []
        self.identificacoes = 0

    def perguntar(self, pergunta, componente, contexto):
        self.contextos.append(contexto)
        cache = contexto.setdefault("cache", {})
        if "identificado" not in cache:
            cache["identificado"] = True
            self.identificacoes += 1
        return {"pergunta": pergunta, "fonte": "contador", "valor": 1}


class Estoura:
    ID = "estoura"

    def perguntar(self, pergunta, componente, contexto):
        raise RuntimeError("bug do adaptador")


class Responde:
    ID = "responde"

    def perguntar(self, pergunta, componente, contexto):
        return {"pergunta": pergunta, "fonte": "responde", "valor": 7}


def _contexto():
    return {"timeout": 20, "http_timeout": 8, "orcamento": 120, "janela": "24h",
            "at": "2026-09-21T10:00:00Z"}


def test_o_cache_sobrevive_entre_as_perguntas_de_um_alvo():
    contador = Contador()
    alvo = {"nome": "prod", "tipo": "docker", "context": "prod"}

    def coletor(alvo_, contexto):
        return {"saude": "🟢", "componentes": [{"nome": "proxy", "papel": "entrada"}]}

    collect.coletar_alvo(alvo, coletor, _contexto(), [contador])

    assert len(contador.contextos) == 3
    assert contador.identificacoes == 1


def test_o_cache_nao_vaza_entre_alvos():
    """Dois alvos podem apontar para o mesmo endereço com credenciais diferentes."""
    contador = Contador()

    def coletor(alvo_, contexto):
        return {"saude": "🟢", "componentes": [{"nome": "proxy", "papel": "entrada"}]}

    contexto = _contexto()
    collect.coletar_alvo({"nome": "a", "tipo": "docker", "context": "a"}, coletor, contexto,
                         [contador])
    collect.coletar_alvo({"nome": "b", "tipo": "docker", "context": "b"}, coletor, contexto,
                         [contador])

    assert contador.identificacoes == 2


def test_o_alvo_chega_no_contexto_da_pergunta():
    contador = Contador()

    def coletor(alvo_, contexto):
        return {"saude": "🟢", "componentes": [{"nome": "proxy", "papel": "entrada"}]}

    collect.coletar_alvo({"nome": "prod", "tipo": "docker", "context": "prod"}, coletor,
                         _contexto(), [contador])

    assert {c["alvo"] for c in contador.contextos} == {"prod"}


def test_http_timeout_chega_limitado_pelo_orcamento():
    contador = Contador()
    componente = {"nome": "proxy", "papel": "entrada", "respostas": []}

    collect.responder(componente, _contexto(), [contador], Prazo(3))

    # orçamento de 3 s: o timeout HTTP de 8 s não pode passar dele
    assert all(c["http_timeout"] <= 3 for c in contador.contextos)


def test_adaptador_que_estoura_nao_impede_o_proximo_de_responder():
    componente = {"nome": "proxy", "papel": "entrada", "respostas": []}

    collect.responder(componente, _contexto(), [Estoura(), Responde()], Prazo(120))

    assert [r.get("valor") for r in componente["respostas"]] == [7, 7, 7]


def test_se_ninguem_responde_o_erro_interno_aparece():
    """Engolir o erro também seria mentir: se nenhum outro responde, o relatório diz que houve
    um bug, e qual."""
    componente = {"nome": "proxy", "papel": "entrada", "respostas": []}

    collect.responder(componente, _contexto(), [Estoura()], Prazo(120))

    assert all(r.get("erro_interno") for r in componente["respostas"])
    assert "bug do adaptador" in componente["respostas"][0]["motivo"]
