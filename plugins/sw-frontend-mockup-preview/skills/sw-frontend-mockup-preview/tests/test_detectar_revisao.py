"""O que a revisão mostrou que o detector deixava passar, acusava errado, ou prometia na
documentação sem cumprir. Cada teste corresponde a um achado dela."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import detectar  # noqa: E402
from test_detectar import mockup, regras  # noqa: E402

VAZIO = '<div class="mock">x</div>'
DESC = 'data-desc="Uma frase sobre a ideia desta variação e o trade-off."'


def com_knob(knob_json, css=""):
    return mockup("<p>x</p>", css).replace(DESC, f"data-desc=\"d\" data-knobs='{knob_json}'", 1)


class VariacaoEAusencia(unittest.TestCase):
    def test_variacao_em_div_tambem_e_analisada(self):
        html = mockup("<button>Salvar — agora</button>")
        html = html.replace('<section class="variation is-active"', '<div class="variation is-active"', 1)
        self.assertIn("travessao-na-interface", regras(html))

    def test_sem_nenhuma_variacao_nao_diz_limpo(self):
        resultado = detectar.analisar("<html><body><p>oi</p></body></html>")
        self.assertEqual(resultado["variacoes"], 0)
        self.assertIn("nenhuma-variacao", [a["regra"] for a in resultado["achados"]])


class Excecao(unittest.TestCase):
    BASE = mockup(VAZIO, ".mock .c { box-shadow: 4px 4px 0 #111; }")

    def declarar(self, texto):
        return self.BASE.replace("<body>", f"<body>\n<!-- detector: {texto} -->", 1)

    def test_aceita_justificativa_travessao_e_ponto_e_virgula(self):
        for texto, esperado in (("ignorar sombra-dura (mundo neobrutalista)", ["sombra-dura"]),
                                ("ignorar sombra-dura — o brief pede", ["sombra-dura"]),
                                ("ignorar sombra-dura; tres-colunas-iguais",
                                 ["sombra-dura", "tres-colunas-iguais"])):
            with self.subTest(texto=texto):
                self.assertEqual(detectar.analisar(self.declarar(texto))["ignoradas"], esperado)

    def test_achado_suprimido_aparece_com_a_linha(self):
        """"Relatado como ignorado, nunca calado": o achado suprimido aparece, com linha e trecho."""
        suprimidos = detectar.analisar(self.declarar("ignorar sombra-dura"))["suprimidos"]
        self.assertEqual([s["regra"] for s in suprimidos], ["sombra-dura"])
        self.assertIn("4px 4px 0", suprimidos[0]["trecho"])

    def test_regra_inexistente_logo_depois_de_ignorar_continua_erro(self):
        with self.assertRaises(ValueError):
            detectar.analisar(self.declarar("ignorar sombra-duraa"))


class Movimento(unittest.TestCase):
    def test_a_palavra_num_paragrafo_nao_vale_como_guarda(self):
        html = mockup("<p>prefers-reduced-motion</p>", ".mock { animation: gira 2s infinite; }")
        html = html.replace("@media (prefers-reduced-motion: reduce)", "@media (min-width: 1px)", 1)
        self.assertIn("sem-reducao-de-movimento", regras(html))


class Css(unittest.TestCase):
    def acusa(self, regra, css):
        self.assertIn(regra, regras(mockup(VAZIO, css)), css)

    def nao_acusa(self, regra, css):
        self.assertNotIn(regra, regras(mockup(VAZIO, css)), css)

    def test_comentario_e_string_no_css_nao_sao_acusados(self):
        self.nao_acusa("preto-puro", ".mock { /* color: #000 */ color: #16181d; }\n"
                                     ".mock::after { content: 'color: #000'; }")

    def test_preto_puro_em_todas_as_grafias(self):
        for css in (".mock{color: rgb(0 0 0)}", ".mock{color:#000000ff}", ".mock{color:#000f}",
                    ".mock{color:hsl(0 0% 0%)}", ".mock{color:rgba(0,0,0,1)}",
                    ".mock{border:1px solid #000}", ".mock{outline:2px solid #000}",
                    ":root{--tinta:#000}"):
            with self.subTest(css=css):
                self.acusa("preto-puro", css)

    def test_preto_translucido_continua_permitido(self):
        self.nao_acusa("preto-puro", ".mock{background:rgb(0 0 0 / .4); color:rgba(0,0,0,.5)}")

    def test_borda_lateral_em_rem_ordem_trocada_e_quatro_valores(self):
        for css in (".a{border-left:0.25rem solid #d33}", ".a{border-left:solid 4px #d33}",
                    ".a{border-width:0 0 0 4px; border-color:#d33}"):
            with self.subTest(css=css):
                self.acusa("borda-lateral-colorida", css)

    def test_borda_lateral_transparente_nao_e_colorida(self):
        self.nao_acusa("borda-lateral-colorida", ".a{border-left:4px solid transparent}")

    def test_fio_de_1px_nao_e_sombra_dura(self):
        self.nao_acusa("sombra-dura", ".a{box-shadow:0 1px 0 rgba(0,0,0,.06)}")

    def test_sombra_dura_com_cor_primeiro(self):
        self.acusa("sombra-dura", ".a{box-shadow:#222 4px 4px 0}")

    def test_sombra_ambiente_neutra_nao_e_halo(self):
        self.nao_acusa("halo-decorativo", ".a{box-shadow:0 0 12px rgba(15,23,42,.08)}")

    def test_halo_em_rem_com_cor_primeiro_e_em_segunda_camada(self):
        for css in (".a{box-shadow:0 0 1.5rem #7c3aed}", ".a{box-shadow:rgb(124 58 237) 0 0 24px}",
                    ".a{box-shadow:0 0 0 1px #e5e7eb, 0 0 24px #7c3aed}"):
            with self.subTest(css=css):
                self.acusa("halo-decorativo", css)

    def test_anel_de_foco_nao_e_halo(self):
        self.nao_acusa("halo-decorativo", ".a:focus-visible{box-shadow:0 0 0 3px #7c3aed}")

    def test_sombra_inset_nao_e_avaliada(self):
        self.nao_acusa("sombra-dura", ".a{box-shadow:inset 4px 4px 0 #111}")

    def test_tres_colunas_com_minmax(self):
        self.acusa("tres-colunas-iguais", ".g{grid-template-columns:repeat(3, minmax(0, 1fr))}")

    def test_a_linha_do_achado_de_css_e_a_da_declaracao(self):
        html = mockup(VAZIO, ".mock {\n  padding: 1rem;\n  color: #000;\n}")
        achado = next(a for a in detectar.analisar(html)["achados"] if a["regra"] == "preto-puro")
        self.assertIn("#000", html.splitlines()[achado["linha"] - 1])


class Utilitarias(unittest.TestCase):
    def test_classes_utilitarias_de_cliche(self):
        for classe, regra in (("grid-cols-3", "tres-colunas-iguais"), ("bg-black", "preto-puro"),
                              ("bg-clip-text", "texto-em-gradiente"),
                              ("border-l-4", "borda-lateral-colorida")):
            with self.subTest(classe=classe):
                self.assertIn(regra, regras(mockup(f'<div class="mock {classe}">x</div>')))


class Texto(unittest.TestCase):
    def acusa(self, regra, markup):
        self.assertIn(regra, regras(mockup(markup)), markup)

    def nao_acusa(self, regra, markup):
        self.assertNotIn(regra, regras(mockup(markup)), markup)

    def test_travessao_em_item_de_navegacao_sem_link(self):
        self.acusa("travessao-na-interface", "<nav><ul><li>Clientes — ativos</li></ul></nav>")

    def test_travessao_em_paragrafo_dentro_de_botao(self):
        self.acusa("travessao-na-interface", "<button><p>Salvar — agora</p></button>")

    def test_travessao_em_titulo_por_classe_e_em_atributo(self):
        for markup in ('<div class="card-title">Pedidos — hoje</div>',
                       '<input placeholder="Nome — completo">',
                       '<button aria-label="Fechar — janela">x</button>',
                       '<input type="submit" value="Enviar — já">'):
            with self.subTest(markup=markup):
                self.acusa("travessao-na-interface", markup)

    def test_meia_risca_de_intervalo_e_correta(self):
        self.nao_acusa("travessao-na-interface", "<label>Horário 08h–18h</label><th>R$ 50–80</th>")

    def test_paragrafo_dentro_de_nav_sem_controle_e_conteudo(self):
        self.nao_acusa("travessao-na-interface",
                       "<nav><p>Cadastre o tutor — depois o pet.</p></nav>")

    def test_emoji_em_paragrafo_dentro_de_botao(self):
        self.acusa("emoji-como-icone", "<button><p>🐶 Cadastrar pet</p></button>")

    def test_emoji_sozinho_fora_de_interface(self):
        self.acusa("emoji-como-icone", "<div>🐶</div>")

    def test_dados_genericos_em_atributo_de_formulario(self):
        for markup in ('<input placeholder="Jane Doe">', '<input value="fulano@exemplo.com.br">',
                       '<input placeholder="(11) 99999-9999">', '<input placeholder="000.000.000-00">'):
            with self.subTest(markup=markup):
                self.acusa("dados-genericos", markup)

    def test_rua_acme_nao_e_empresa_generica(self):
        self.nao_acusa("dados-genericos", "<p>Rua Acme, 12</p>")

    def test_contagem_com_zero_a_esquerda_nao_e_rotulo(self):
        self.nao_acusa("rotulo-numerado", "<span>02 animais</span><span>03 vacinas pendentes</span>")

    def test_numero_com_simbolo_de_numero(self):
        self.acusa("rotulo-numerado", '<span class="eyebrow">№ 1 · Serviços</span>')

    def test_eleve_o_tambem_e_enchimento(self):
        self.acusa("verbo-de-enchimento", "<h1>Eleve o atendimento</h1>")


class Knobs(unittest.TestCase):
    def test_knob_declarado_sem_css_e_acusado(self):
        """Declarar o knob e esquecer o CSS deixava um controle que não faz nada, sem aviso."""
        html = com_knob('[{"id":"ficha","tipo":"toggle","padrao":false,"rotulo":"Ficha"}]')
        self.assertIn("knob-sem-efeito", regras(html))

    def test_knob_usado_no_css_nao_e_acusado(self):
        html = com_knob('[{"id":"acento","tipo":"range","padrao":0.5,"rotulo":"A"}]',
                        ".mock{opacity:var(--k-acento,.5)}")
        self.assertNotIn("knob-sem-efeito", regras(html))

    def test_knob_steps_usado_pelo_atributo(self):
        html = com_knob('[{"id":"lista","tipo":"steps","opcoes":["a","b"],"padrao":"a","rotulo":"L"}]',
                        '.variation[data-k-lista="b"] .mock{gap:0}')
        self.assertNotIn("knob-sem-efeito", regras(html))


if __name__ == "__main__":
    unittest.main()
