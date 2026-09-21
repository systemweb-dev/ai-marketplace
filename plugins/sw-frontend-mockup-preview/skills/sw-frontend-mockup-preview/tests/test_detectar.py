"""Testes do detector anti-slop (`scripts/detectar.py`).

Rodam só com a biblioteca padrão: `python3 -m unittest discover -s tests`.

Cada regra tem um caso positivo, e há um HTML limpo que não pode acusar nada: detector que
acusa demais é desligado pelo usuário, e aí não serve para nada.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import detectar  # noqa: E402

CASCA = (RAIZ / "assets" / "harness.html").read_text(encoding="utf-8")


def mockup(markup="", css="", fora=""):
    """Um mockup montado sobre o harness real: CSS do design no lugar dele, markup numa
    variação. `fora` entra fora da variação (casca)."""
    html = CASCA.replace(
        "     @container (max-width: 480px) { ... } — the viewport toggle drives it.\n"
        "     ============================================================ */\n",
        "     @container (max-width: 480px) { ... } — the viewport toggle drives it.\n"
        "     ============================================================ */\n" + css + "\n", 1)
    alvo = ("        <!-- <div class=\"mock\"> ...component markup, using var(--bg-card) "
            "etc... </div> -->")
    assert alvo in html, "o template do harness mudou: o ponto de inserção sumiu"
    html = html.replace(alvo, "        " + markup, 1)
    html = html.replace('<div class="hz-caption" id="hz-caption"></div>',
                        '<div class="hz-caption" id="hz-caption"></div>' + fora, 1)
    return html


LIMPO_CSS = """
.mock { color: #16181d; background: var(--bg-card); padding: 2rem; }
.mock h1 { font-size: 2.4rem; letter-spacing: -0.02em; }
.mock .card { box-shadow: 0 8px 24px rgb(20 22 30 / 0.08); border: 1px solid #e3e5ea;
              transition: transform .3s cubic-bezier(0.16, 1, 0.3, 1); }
.mock .grade { display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem; }
"""
LIMPO_HTML = """<div class="mock">
  <h1>Pedidos da semana</h1>
  <p>Heloísa Tavares fechou 47 pedidos — dois a mais que na semana passada.</p>
  <div class="grade"><div class="card"><h2>R$ 18.412,30 em vendas</h2>
    <p>Ticket médio de R$ 391,75.</p></div></div>
  <button>Exportar relatório</button>
</div>"""


def regras(html):
    return sorted({a["regra"] for a in detectar.analisar(html)["achados"]})


class Limpo(unittest.TestCase):
    def test_mockup_limpo_nao_acusa_nada(self):
        self.assertEqual(regras(mockup(LIMPO_HTML, LIMPO_CSS)), [])

    def test_o_harness_sozinho_nao_acusa_nada(self):
        """A casca usa emoji nos botões e tem CSS próprio. Nada disso é design."""
        self.assertEqual(regras(CASCA), [])

    def test_travessao_em_paragrafo_e_permitido(self):
        """Em português o travessão é pontuação legítima em texto corrido."""
        self.assertNotIn("travessao-na-interface",
                         regras(mockup("<p>Dois pedidos — ambos pagos.</p>")))

    def test_o_que_fica_fora_da_variacao_nao_e_analisado(self):
        html = mockup(LIMPO_HTML, LIMPO_CSS, fora="<button>Salvar — agora</button>")
        self.assertNotIn("travessao-na-interface", regras(html))


class RegrasDeCss(unittest.TestCase):
    def acusa(self, regra, css="", markup='<div class="mock">x</div>'):
        self.assertIn(regra, regras(mockup(markup, css)))

    def test_texto_em_gradiente(self):
        self.acusa("texto-em-gradiente", ".mock h1 { background: linear-gradient(red, blue); "
                   "-webkit-background-clip: text; color: transparent; }")

    def test_preto_puro(self):
        self.acusa("preto-puro", ".mock { color: #000; }")
        self.acusa("preto-puro", ".mock { background: #000000; }")
        self.acusa("preto-puro", ".mock { background-color: black; }")
        self.acusa("preto-puro", ".mock { color: rgb(0, 0, 0); }")

    def test_preto_translucido_em_sombra_nao_e_preto_puro(self):
        self.assertNotIn("preto-puro", regras(mockup(
            '<div class="mock">x</div>', ".mock { box-shadow: 0 4px 12px rgba(0,0,0,.12); }")))

    def test_cor_que_so_comeca_com_000_nao_e_preto(self):
        self.assertNotIn("preto-puro", regras(mockup(
            '<div class="mock">x</div>', ".mock { color: #0000ff; background: #000a14; }")))

    def test_borda_lateral_colorida(self):
        self.acusa("borda-lateral-colorida", ".mock .aviso { border-left: 4px solid #d33; }")
        self.acusa("borda-lateral-colorida", ".mock .aviso { border-right-width: 3px; }")

    def test_borda_lateral_de_1px_e_permitida(self):
        self.assertNotIn("borda-lateral-colorida", regras(mockup(
            '<div class="mock">x</div>', ".mock { border-left: 1px solid #ddd; }")))

    def test_sombra_dura(self):
        self.acusa("sombra-dura", ".mock .card { box-shadow: 4px 4px 0 #111; }")

    def test_halo_decorativo(self):
        self.acusa("halo-decorativo", ".mock .card { box-shadow: 0 0 24px #7c3aed; }")

    def test_easing_elastico(self):
        self.acusa("easing-elastico",
                   ".mock { transition: all .4s cubic-bezier(.68,-0.55,.27,1.55); }")

    def test_cursor_personalizado(self):
        self.acusa("cursor-personalizado", ".mock { cursor: url(seta.png), auto; }")

    def test_tres_colunas_iguais(self):
        self.acusa("tres-colunas-iguais", ".mock .g { grid-template-columns: repeat(3, 1fr); }")
        self.acusa("tres-colunas-iguais", ".mock .g { grid-template-columns: 1fr 1fr 1fr; }")

    def test_estilo_inline_dentro_da_variacao_tambem_e_analisado(self):
        self.assertIn("preto-puro", regras(mockup('<div class="mock" style="color:#000">x</div>')))

    def test_sem_reducao_de_movimento(self):
        html = mockup('<div class="mock">x</div>', ".mock { animation: gira 2s infinite; }")
        html = html.replace("prefers-reduced-motion", "prefers-color-scheme")
        self.assertIn("sem-reducao-de-movimento", regras(html))

    def test_guarda_de_movimento_do_harness_vale(self):
        """A guarda global mora na casca, e ela cobre as animações do design."""
        self.assertNotIn("sem-reducao-de-movimento", regras(mockup(
            '<div class="mock">x</div>', ".mock { animation: gira 2s infinite; }")))


class RegrasDeTexto(unittest.TestCase):
    def acusa(self, regra, markup):
        self.assertIn(regra, regras(mockup(markup)))

    def test_travessao_em_botao_titulo_rotulo_e_link(self):
        for markup in ("<button>Salvar — agora</button>", "<h2>Vendas — semana</h2>",
                       "<label>Nome – completo</label>", '<a href="#">Ver — todos</a>',
                       '<span class="badge">Novo — beta</span>', "<th>Total — mês</th>"):
            with self.subTest(markup=markup):
                self.acusa("travessao-na-interface", markup)

    def test_rotulo_numerado(self):
        for texto in ("01 / Recursos", "002 · Serviços", "03", "04. Como funciona"):
            with self.subTest(texto=texto):
                self.acusa("rotulo-numerado", f'<span class="eyebrow">{texto}</span>')

    def test_hora_e_data_nao_sao_rotulo_numerado(self):
        html = mockup('<span>09:30</span><span>05/10/2026</span><td>07</td>')
        self.assertNotIn("rotulo-numerado", regras(html))

    def test_emoji_como_icone(self):
        self.acusa("emoji-como-icone", "<button>🚀 Começar</button>")
        self.acusa("emoji-como-icone", '<span class="icone">⚙️</span>')

    def test_emoji_em_mensagem_de_chat_e_conteudo(self):
        self.assertNotIn("emoji-como-icone", regras(mockup("<p>Chegou! 🎉</p>")))

    def test_dados_genericos(self):
        for texto in ("John Doe", "Jane Doe", "Fulano de Tal", "Lorem ipsum dolor", "Acme",
                      "contato@example.com"):
            with self.subTest(texto=texto):
                self.acusa("dados-genericos", f"<p>{texto}</p>")

    def test_numero_perfeito_demais(self):
        self.acusa("numero-perfeito-demais", "<strong>99,99%</strong>")
        self.acusa("numero-perfeito-demais", "<td>1234567</td>")

    def test_verbo_de_enchimento(self):
        self.acusa("verbo-de-enchimento", "<h1>Revolucione sua gestão</h1>")
        self.acusa("verbo-de-enchimento", "<p>A seamless experience</p>")


class Resultado(unittest.TestCase):
    def test_achado_traz_linha_trecho_e_dica(self):
        html = mockup("<button>Salvar — agora</button>")
        achado = next(a for a in detectar.analisar(html)["achados"]
                      if a["regra"] == "travessao-na-interface")
        linha = html.splitlines()[achado["linha"] - 1]
        self.assertIn("Salvar", linha)
        self.assertIn("Salvar", achado["trecho"])
        self.assertTrue(achado["dica"])

    def test_severidade_de_cada_regra_e_falha_ou_aviso(self):
        for regra in detectar.REGRAS.values():
            self.assertIn(regra["severidade"], ("falha", "aviso"))

    def test_ignorar_por_comentario_e_relatado_nunca_calado(self):
        html = mockup('<div class="mock">x</div>', ".mock .c { box-shadow: 4px 4px 0 #111; }")
        html = html.replace("<body>", "<body>\n<!-- detector: ignorar sombra-dura -->", 1)
        resultado = detectar.analisar(html)
        self.assertNotIn("sombra-dura", [a["regra"] for a in resultado["achados"]])
        self.assertEqual(resultado["ignoradas"], ["sombra-dura"])

    def test_ignorar_regra_que_nao_existe_e_erro(self):
        html = mockup().replace("<body>", "<body>\n<!-- detector: ignorar sombra-duraa -->", 1)
        with self.assertRaises(ValueError):
            detectar.analisar(html)


class Linha(unittest.TestCase):
    def rodar(self, html, *extra, tmp="mock.html"):
        caminho = Path(self._tmp) / tmp
        caminho.write_text(html, encoding="utf-8")
        return subprocess.run([sys.executable, str(RAIZ / "scripts" / "detectar.py"),
                               str(caminho), *extra], capture_output=True, text=True)

    def setUp(self):
        import tempfile

        self._tmp = tempfile.mkdtemp()

    def test_limpo_sai_com_zero(self):
        self.assertEqual(self.rodar(mockup(LIMPO_HTML, LIMPO_CSS)).returncode, 0)

    def test_falha_sai_com_dois(self):
        self.assertEqual(self.rodar(mockup("<button>Salvar — agora</button>")).returncode, 2)

    def test_so_aviso_sai_com_zero_mas_mostra(self):
        r = self.rodar(mockup('<div class="mock">x</div>',
                              ".mock .c { box-shadow: 0 0 24px #7c3aed; }"))
        self.assertEqual(r.returncode, 0)
        self.assertIn("halo-decorativo", r.stdout)

    def test_arquivo_que_nao_existe_sai_com_um(self):
        r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "detectar.py"),
                            "/caminho/que/nao/existe.html"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)

    def test_saida_json(self):
        r = self.rodar(mockup("<button>Salvar — agora</button>"), "--json")
        dados = json.loads(r.stdout)
        self.assertIn("travessao-na-interface", [a["regra"] for a in dados["achados"]])


class Isolamento(unittest.TestCase):
    def test_nao_importa_rede_nem_subprocesso(self):
        """O detector lê um arquivo local e nada mais."""
        import ast

        arvore = ast.parse((RAIZ / "scripts" / "detectar.py").read_text(encoding="utf-8"))
        nomes = {alias.name.split(".")[0] for no in ast.walk(arvore)
                 if isinstance(no, (ast.Import, ast.ImportFrom))
                 for alias in (no.names if isinstance(no, ast.Import) else [no])
                 if getattr(alias, "name", None)}
        nomes |= {no.module.split(".")[0] for no in ast.walk(arvore)
                  if isinstance(no, ast.ImportFrom) and no.module}
        self.assertFalse(nomes & {"urllib", "socket", "http", "requests", "subprocess"}, nomes)



class Fronteira(unittest.TestCase):
    """A casca do harness divide o `<style>` com o design. Sem fronteira, um mockup nasceria
    com achados que não são dele — e o usuário desligaria o detector."""

    def test_tell_dentro_da_casca_nao_e_acusado(self):
        html = CASCA.replace("  /* harness:fim */", "  .hz-x { color: #000; }\n  /* harness:fim */", 1)
        self.assertNotIn("preto-puro", regras(html))

    def test_o_mesmo_tell_fora_da_casca_e_acusado(self):
        self.assertIn("preto-puro", regras(mockup('<div class="mock">x</div>',
                                                  ".mock { color: #000; }")))

    def test_mockup_antigo_sem_marcadores_tambem_tem_fronteira(self):
        """Mockups gerados antes dos marcadores usam o comentário antigo da casca."""
        antigo = (CASCA.replace("  /* harness:inicio — casca do preview, não é design. O detector "
                                "(scripts/detectar.py)\n     ignora tudo até harness:fim; escreva o "
                                "CSS do mockup DEPOIS dele. */",
                                "  /* ---- harness chrome (not part of the design) ---- */")
                  .replace("  /* harness:fim */\n", ""))
        self.assertNotIn("harness:inicio", antigo)
        antigo = antigo.replace("  .variation { display: none; }",
                                "  .hz-x { color: #000; }\n  .variation { display: none; }", 1)
        self.assertNotIn("preto-puro", regras(antigo))


if __name__ == "__main__":
    unittest.main()
