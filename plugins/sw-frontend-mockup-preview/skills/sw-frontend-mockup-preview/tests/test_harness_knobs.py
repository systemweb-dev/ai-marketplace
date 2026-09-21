"""Knobs no harness: cada variação declara de 0 a 4 ajustes, e o canvas desenha os controles.

Estes testes EXECUTAM o JavaScript do harness num Chrome headless e leem o DOM que sobra
(`--dump-dom`). Pulam sozinhos quando não há Chrome na máquina.
"""
import html as html_mod
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CASCA = (RAIZ / "assets" / "harness.html").read_text(encoding="utf-8")
CHROME = next((c for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)),
              None)


def com_variacoes(*secoes):
    """O harness real com as seções dadas no lugar da variação de exemplo."""
    inicio = CASCA.index("      <section class=\"variation is-active\"")
    fim = CASCA.index("      <!-- Duplicate for more variations:")
    return CASCA[:inicio] + "\n".join(secoes) + "\n" + CASCA[fim:]


def secao(n, knobs=None, ativa=False, corpo="<p>x</p>"):
    atributo = f" data-knobs='{json.dumps(knobs, ensure_ascii=False)}'" if knobs is not None else ""
    classe = "variation is-active" if ativa else "variation"
    return (f'      <section class="{classe}" data-title="V{n}" data-desc="d"{atributo}>'
            f"{corpo}</section>")


@unittest.skipUnless(CHROME, "sem Chrome na máquina")
class Knobs(unittest.TestCase):
    def dom(self, html, consulta=""):
        pasta = Path(tempfile.mkdtemp())
        (pasta / "index.html").write_text(html, encoding="utf-8")
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                            "--virtual-time-budget=2000", "--dump-dom",
                            (pasta / "index.html").as_uri() + consulta],
                           capture_output=True, text=True, timeout=60)
        return r.stdout

    def secao_no_dom(self, dom, n):
        inicio = dom.index(f'data-title="V{n}"')
        return dom[dom.rfind("<section", 0, inicio):dom.index(">", inicio) + 1]

    def barra(self, dom):
        inicio = dom.index('id="hz-knobs"')
        return dom[dom.rfind("<div", 0, inicio):dom.index("</div><!-- /hz-knobs -->", inicio)]

    RANGE = {"id": "acento", "tipo": "range", "min": 0, "max": 1, "passo": 0.1, "padrao": 0.5,
             "rotulo": "Quantidade de acento"}
    STEPS = {"id": "densidade", "tipo": "steps", "opcoes": ["arejada", "compacta"],
             "padrao": "arejada", "rotulo": "Densidade"}
    TOGGLE = {"id": "serifa", "tipo": "toggle", "padrao": False, "rotulo": "Título serifado"}

    def test_range_aplica_o_padrao_como_variavel_css(self):
        dom = self.dom(com_variacoes(secao(1, [self.RANGE], ativa=True)))

        self.assertIn("--k-acento: 0.5", self.secao_no_dom(dom, 1))
        self.assertIn('type="range"', self.barra(dom))
        self.assertIn("Quantidade de acento", self.barra(dom))

    def test_steps_vira_atributo(self):
        dom = self.dom(com_variacoes(secao(1, [self.STEPS], ativa=True)))

        self.assertIn('data-k-densidade="arejada"', self.secao_no_dom(dom, 1))

    def test_toggle_vira_variavel_zero_ou_um(self):
        dom = self.dom(com_variacoes(secao(1, [self.TOGGLE], ativa=True)))

        self.assertIn("--k-serifa: 0", self.secao_no_dom(dom, 1))

    def test_valor_pela_url_para_screenshot_sem_clique(self):
        """`?k=acento:0.8,densidade:compacta` abre direto no estado — é o que permite a
        auto-conferência capturar um ajuste sem clicar."""
        dom = self.dom(com_variacoes(secao(1, [self.RANGE, self.STEPS], ativa=True)),
                       "?k=acento:0.8,densidade:compacta")

        self.assertIn("--k-acento: 0.8", self.secao_no_dom(dom, 1))
        self.assertIn('data-k-densidade="compacta"', self.secao_no_dom(dom, 1))

    def test_cada_variacao_mostra_os_proprios_knobs(self):
        dom = self.dom(com_variacoes(secao(1, [self.RANGE], ativa=True), secao(2, [self.STEPS])),
                       "?v=2")

        self.assertIn("Densidade", self.barra(dom))
        self.assertNotIn("Quantidade de acento", self.barra(dom))

    def test_variacao_sem_knobs_esconde_a_barra(self):
        """Compatível com os mockups de antes: sem `data-knobs`, nada muda."""
        dom = self.dom(com_variacoes(secao(1, None, ativa=True)))

        self.assertRegex(self.barra(dom), r'id="hz-knobs"[^>]*hidden')

    def test_mais_de_quatro_knobs_mostra_so_quatro_e_avisa(self):
        knobs = [dict(self.RANGE, id=f"k{i}", rotulo=f"Ajuste {i}") for i in range(6)]
        dom = self.dom(com_variacoes(secao(1, knobs, ativa=True)))

        self.assertEqual(self.barra(dom).count('type="range"'), 4)
        self.assertIn("só os 4 primeiros", self.barra(dom))

    def test_json_invalido_avisa_e_nao_quebra_o_harness(self):
        quebrado = ('      <section class="variation is-active" data-title="V1" data-desc="d" '
                    "data-knobs='[{\"id\": '><p>x</p></section>")
        dom = self.dom(com_variacoes(quebrado, secao(2, [self.RANGE])))

        self.assertIn("inválido", self.barra(dom))
        self.assertIn('class="hz-btn hz-tab', dom, "as abas pararam de ser montadas")

    def test_rotulo_e_texto_nunca_html(self):
        malicioso = dict(self.RANGE, rotulo="<img src=x onerror=alert(1)>")
        dom = self.dom(com_variacoes(secao(1, [malicioso], ativa=True)))

        self.assertNotIn("<img src=", self.barra(dom))
        self.assertIn("&lt;img", self.barra(dom))

    def test_id_fora_do_formato_e_recusado(self):
        """O id vira nome de variável CSS e de atributo: `a;b` quebraria o estilo."""
        dom = self.dom(com_variacoes(secao(1, [dict(self.RANGE, id="a;b")], ativa=True)))

        self.assertNotIn("--k-a;b", dom)
        self.assertIn("id inválido", self.barra(dom))


    # --- o que a revisão mostrou ---
    def test_toggle_com_padrao_false_em_texto_abre_desligado(self):
        """`!!"false"` é verdadeiro em JavaScript: o toggle abria ligado."""
        dom = self.dom(com_variacoes(secao(1, [dict(self.TOGGLE, padrao="false")], ativa=True)))

        self.assertIn("--k-serifa: 0", self.secao_no_dom(dom, 1))
        self.assertNotIn("data-k-serifa", self.secao_no_dom(dom, 1))

    def test_valor_fora_da_faixa_e_limitado(self):
        """`?k=acento:7` com max=1 gravava 7 na variável, e o slider mostrava 1: a barra mentia."""
        dom = self.dom(com_variacoes(secao(1, [self.RANGE], ativa=True)), "?k=acento:7")

        self.assertIn("--k-acento: 1", self.secao_no_dom(dom, 1))
        self.assertNotIn(">7<", self.barra(dom))

    def test_valor_que_nao_e_numero_volta_ao_padrao(self):
        dom = self.dom(com_variacoes(secao(1, [self.RANGE], ativa=True)), "?k=acento:abc")

        self.assertIn("--k-acento: 0.5", self.secao_no_dom(dom, 1))
        self.assertNotIn("abc", self.barra(dom))

    def test_opcao_fora_da_lista_e_recusada(self):
        dom = self.dom(com_variacoes(secao(1, [self.STEPS], ativa=True)), "?k=densidade:gigante")

        self.assertIn('data-k-densidade="arejada"', self.secao_no_dom(dom, 1))

    def test_opcao_com_dois_pontos_pela_url(self):
        formatos = dict(self.STEPS, id="formato", opcoes=["16:9", "4:3"], padrao="16:9",
                        rotulo="Formato")
        dom = self.dom(com_variacoes(secao(1, [formatos], ativa=True)), "?k=formato:4:3")

        self.assertIn('data-k-formato="4:3"', self.secao_no_dom(dom, 1))

    def test_toggle_aceita_on_e_sim(self):
        for bruto in ("on", "sim", "true", "1"):
            with self.subTest(bruto=bruto):
                dom = self.dom(com_variacoes(secao(1, [self.TOGGLE], ativa=True)),
                               f"?k=serifa:{bruto}")
                self.assertIn("--k-serifa: 1", self.secao_no_dom(dom, 1))

    def test_steps_sem_opcoes_e_tipo_desconhecido_sao_avisados(self):
        dom = self.dom(com_variacoes(secao(1, [
            {"id": "a", "tipo": "steps", "rotulo": "A"},
            {"id": "b", "tipo": "slider", "rotulo": "B"}], ativa=True)))

        self.assertNotIn('data-k-a="undefined"', dom)
        self.assertIn("sem opções", self.barra(dom))
        self.assertIn("tipo", self.barra(dom))

    def test_id_repetido_na_mesma_variacao_e_avisado(self):
        dom = self.dom(com_variacoes(secao(1, [self.RANGE, dict(self.RANGE, rotulo="De novo")],
                                           ativa=True)))

        self.assertEqual(self.barra(dom).count('type="range"'), 1)
        self.assertIn("repetido", self.barra(dom))

    def test_valor_guardado_ao_trocar_de_aba(self):
        """A SKILL promete que cada variação guarda os próprios valores ao trocar de aba."""
        pagina = com_variacoes(secao(1, [self.RANGE], ativa=True), secao(2, [self.STEPS]))
        pagina = pagina.replace("</script>",
                                "document.querySelectorAll('.hz-tab')[1].click();"
                                "document.querySelectorAll('.hz-tab')[0].click();</script>", 1)
        dom = self.dom(pagina, "?k=acento:0.8")

        self.assertIn('value="0.8"', self.barra(dom).replace("0.80", "0.8"))

    def test_limpo_esconde_a_casca_para_screenshot(self):
        dom = self.dom(com_variacoes(secao(1, [self.RANGE], ativa=True)), "?limpo=1")

        self.assertRegex(dom, r'<body[^>]*data-limpo')


if __name__ == "__main__":
    unittest.main()
