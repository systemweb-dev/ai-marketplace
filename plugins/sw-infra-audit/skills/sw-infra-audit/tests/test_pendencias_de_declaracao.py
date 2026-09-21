# tests/test_pendencias_de_declaracao.py
"""O relatório precisa dizer por que está vazio.

Numa auditoria real, 57 componentes entraram no relatório e 55 não receberam pergunta nenhuma;
os 2 que receberam responderam `sem_dados` porque o `alvos.toml` não declarava `metricas_url`.
O relatório mostrou nomes e silêncio, e quem leu concluiu que a skill não funcionava.

O silêncio tem causa, e a causa é acionável: falta uma linha no `alvos.toml`. Dizer isso é o
que separa "sem dados" de "sem explicação".
"""
from build_report import pendencias_de_declaracao, _pendencias


def _alvo(nome, componentes):
    return {"nome": nome, "componentes": componentes}


def _comp(nome, papel, respostas):
    return {"nome": nome, "papel": papel, "respostas": respostas}


SEM_FONTE = {"pergunta": "entrada.latencia", "sem_dados": True,
             "motivo": "o componente não declara `metricas_url` no alvos.toml"}


def test_agrupa_componentes_que_esperam_a_mesma_declaracao():
    alvos = [_alvo("prod", [_comp("traefik", "entrada", [SEM_FONTE]),
                            _comp("nginx", "entrada", [SEM_FONTE])])]

    pend = pendencias_de_declaracao(alvos)

    assert len(pend) == 1
    assert pend[0]["motivo"] == "o componente não declara `metricas_url` no alvos.toml"
    assert sorted(c["componente"] for c in pend[0]["componentes"]) == ["nginx", "traefik"]


def test_componente_sem_nenhuma_pergunta_tambem_e_pendencia():
    """O caso mais comum e o mais invisível: papel sem pergunta registrada não gera nem
    `sem_dados` — gera lista vazia, e o componente some do relatório sem deixar rastro."""
    # `cache` e `banco` seguem sem pergunta registrada. (`fila` servia de exemplo aqui até o
    # plano 2 dar a ela quatro perguntas — o exemplo precisa ser um papel que continue mudo.)
    alvos = [_alvo("prod", [_comp("redis", "cache", []),
                            _comp("postgres", "banco", [])])]

    pend = pendencias_de_declaracao(alvos)

    papeis = {p["papel"] for p in pend}
    assert papeis == {"cache", "banco"}
    assert all("nenhuma pergunta" in p["motivo"] for p in pend)


def test_componente_que_respondeu_nao_vira_pendencia():
    respondeu = {"pergunta": "entrada.latencia", "valor": 210, "fonte": "promql"}
    alvos = [_alvo("prod", [_comp("traefik", "entrada", [respondeu])])]

    assert pendencias_de_declaracao(alvos) == []


def test_pendencia_parcial_conta_so_a_pergunta_sem_resposta():
    """Um componente pode responder uma pergunta e falhar noutra. Some-lo inteiro esconderia
    a lacuna; ignorá-lo inteiro inventaria uma lacuna que não existe."""
    alvos = [_alvo("prod", [_comp("traefik", "entrada",
                                  [{"pergunta": "entrada.latencia", "valor": 9},
                                   SEM_FONTE])])]

    pend = pendencias_de_declaracao(alvos)

    assert len(pend) == 1 and len(pend[0]["componentes"]) == 1


def test_html_nomeia_o_componente_e_o_que_falta():
    alvos = [_alvo("prod", [_comp("traefik", "entrada", [SEM_FONTE])])]

    html = _pendencias(alvos)

    assert "traefik" in html and "metricas_url" in html


def test_sem_pendencia_o_bloco_diz_que_esta_completo():
    alvos = [_alvo("prod", [_comp("traefik", "entrada",
                                  [{"pergunta": "entrada.latencia", "valor": 1}])])]

    html = _pendencias(alvos)

    assert "traefik" not in html


def test_papel_que_ganhou_pergunta_deixa_de_ser_pendencia_de_papel():
    """`fila` ganhou perguntas no plano 2: um componente `fila` nunca mais pode aparecer com o
    motivo "papel sem pergunta".

    O componente vem SEM respostas de propósito — é esse o caminho que decide "papel sem
    pergunta". A primeira versão deste teste trazia respostas preenchidas, então o ramo nunca
    rodava, e apagar as quatro perguntas de `fila` não derrubava nada.
    """
    alvos = [_alvo("prod", [_comp("broker", "fila", [])])]

    pend = pendencias_de_declaracao(alvos)

    assert not any("papel `fila`" in p["motivo"] for p in pend)


def test_insight_so_existe_para_componente_que_tem_o_que_dizer():
    """Antes, cada um dos 57 componentes ganhava um cartão inteiro para dizer "nenhuma pergunta
    para este papel nesta versão" — seis páginas A4 da mesma frase. Essa informação é uma
    pendência de declaração, e já é contada uma vez na seção própria."""
    from build_report import _insights_v3

    alvos = [_alvo("prod", [_comp("mudo", "app", []),
                            _comp("falante", "entrada",
                                  [{"pergunta": "entrada.latencia", "valor": 7,
                                    "fonte": "promql"}])])]

    html = _insights_v3(alvos)

    assert "falante" in html
    assert "mudo" not in html
    assert "nenhuma pergunta" not in html


def test_insight_mantem_componente_que_so_tem_analise():
    """Sem resposta, mas com análise escrita pelo agente: aí há o que ler."""
    from build_report import _insights_v3

    alvos = [_alvo("prod", [_comp("analisado", "app", []) | {"analise": "roda em réplica única"}])]

    html = _insights_v3(alvos)

    assert "analisado" in html and "réplica única" in html


def test_insight_conta_quantos_ficaram_de_fora():
    """Omitir em silêncio seria trocar um exagero por uma omissão."""
    from build_report import _insights_v3

    alvos = [_alvo("prod", [_comp(f"mudo-{n}", "app", []) for n in range(9)]
                   + [_comp("falante", "entrada",
                            [{"pergunta": "entrada.latencia", "valor": 7, "fonte": "promql"}])])]

    html = _insights_v3(alvos)

    assert "9" in html and "falta declarar" in html.lower()


def test_motivo_da_pendencia_renderiza_o_codigo_inline():
    """O motivo cita nomes de campo entre crases (`metricas_url`). Escapado cru, as crases
    aparecem no papel e o relatório parece rascunho."""
    alvos = [_alvo("prod", [_comp("traefik", "entrada", [SEM_FONTE])])]

    html = _pendencias(alvos)

    assert "<code>metricas_url</code>" in html
    assert "`" not in html
