"""A tela do harness: estado na URL, comparar, larguras, atalhos, fontes, direção, e a conversa
pela tela (comentários, escolha, achado que aponta o elemento).

Executa o JavaScript real do harness num Chrome headless. Uma "sonda" (script extra antes do
</body>) roda depois do harness, faz as perguntas e escreve a resposta em JSON num <pre>, que o
teste lê do `--dump-dom`. Os testes de conversa sobem o serve.py de verdade, em processo.
Pulam sozinhos quando não há Chrome na máquina.
"""
import html as html_mod
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import serve  # noqa: E402

CASCA = (RAIZ / "assets" / "harness.html").read_text(encoding="utf-8")
CHROME = next((c for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)),
              None)
KNOB = {"id": "acento", "tipo": "range", "min": 0, "max": 1, "passo": 0.1, "padrao": 0.5}


def pagina(*secoes, estilo=""):
    inicio = CASCA.index("      <section class=\"variation is-active\"")
    fim = CASCA.index("      <!-- Duplicate for more variations:")
    html = CASCA[:inicio] + "\n".join(secoes) + "\n" + CASCA[fim:]
    return html.replace("</style>", estilo + "\n</style>", 1) if estilo else html


def secao(n, corpo="<p>texto</p>", ativa=False, knobs=None):
    classe = "variation is-active" if ativa else "variation"
    atributo = f" data-knobs='{json.dumps(knobs)}'" if knobs else ""
    return f'      <section class="{classe}" data-title="V{n}" data-desc="d"{atributo}>{corpo}</section>'


TRES = [secao(1, "<h2>Título um</h2><p>corpo um</p>", ativa=True, knobs=[KNOB]),
        secao(2, "<h2>Título dois</h2><p>corpo dois</p>"),
        secao(3, "<h2>Título três</h2><p>corpo três</p>")]


def com_sonda(html, corpo_js, espera=600):
    sonda = ("<script>setTimeout(async () => { let r; try { r = await (async () => {"
             + corpo_js + "})(); } catch (e) { r = {erro: String(e)}; }"
             " const p = document.createElement('pre'); p.id = 'sonda';"
             " p.textContent = JSON.stringify(r); document.body.appendChild(p); }, "
             + str(espera) + ");</script>\n</body>")
    return html.replace("</body>", sonda, 1)


def resposta(dom):
    m = re.search(r'<pre id="sonda">(.*?)</pre>', dom, re.S)
    if not m:
        raise AssertionError("a sonda não respondeu:\n" + dom[-1500:])
    return json.loads(html_mod.unescape(m.group(1)))


@unittest.skipUnless(CHROME, "sem Chrome na máquina")
class Tela(unittest.TestCase):
    """Aberto como arquivo: tudo que não depende do servidor."""

    def sondar(self, html, corpo_js, consulta=""):
        pasta = Path(tempfile.mkdtemp())
        (pasta / "index.html").write_text(com_sonda(html, corpo_js), encoding="utf-8")
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                            "--window-size=1400,900", "--virtual-time-budget=3000", "--dump-dom",
                            (pasta / "index.html").as_uri() + consulta],
                           capture_output=True, text=True, timeout=60)
        return resposta(r.stdout)

    def test_cada_clique_vai_para_a_url(self):
        """O live-reload recarrega a mesma URL: é assim que a tela não volta ao início a cada edição."""
        r = self.sondar(pagina(*TRES), "activate(1); setVw('mobile'); setTheme('dark'); return location.search;")

        self.assertIn("v=2", r)
        self.assertIn("vw=mobile", r)
        self.assertIn("theme=dark", r)

    def test_estado_inicial_da_url_nao_e_apagado_ao_carregar(self):
        r = self.sondar(pagina(*TRES), """return {url: location.search, ativa,
            vw: stage.dataset.vw, tema: frame.dataset.theme};""", "?v=2&vw=tablet&theme=dark")

        self.assertIn("v=2", r["url"])
        self.assertIn("vw=tablet", r["url"])
        self.assertIn("theme=dark", r["url"])
        self.assertEqual([r["ativa"], r["vw"], r["tema"]], [1, "tablet", "dark"])

    def test_knob_mudado_vai_para_a_url_e_o_padrao_nao(self):
        r = self.sondar(pagina(*TRES), """
            const antes = location.search;
            aplicarKnob(variations[0], lerKnobs(variations[0]).lista[0], 0.8);
            return [antes, location.search];""")

        self.assertNotIn("k=", r[0])
        self.assertIn("k=acento:0.8", r[1])

    def test_comparar_mostra_todas_e_nenhuma_aba_ativa(self):
        r = self.sondar(pagina(*TRES), """return {
            visiveis: variations.filter(v => getComputedStyle(v).display !== 'none').length,
            abasAtivas: document.querySelectorAll('.hz-tab.is-active').length,
            url: location.search};""", "?comparar=1")

        self.assertEqual(r["visiveis"], 3)
        self.assertEqual(r["abasAtivas"], 0)
        self.assertIn("comparar=1", r["url"])

    def test_clicar_numa_aba_sai_do_comparar(self):
        r = self.sondar(pagina(*TRES), """
            document.querySelectorAll('.hz-tab')[2].click();
            return {comparando: comparando(), visiveis: variations.filter(v => getComputedStyle(v).display !== 'none').length};""",
            "?comparar=1")

        self.assertEqual(r, {"comparando": False, "visiveis": 1})

    def test_painel_mostra_uma_aba_por_vez(self):
        r = self.sondar(pagina(*TRES), """
            const visiveis = () => Array.from(document.querySelectorAll('.hz-pane')).filter(p => !p.hidden).map(p => p.id);
            const antes = visiveis();
            $('hz-aba-direcao').click();
            return {antes, depois: visiveis(), marcada: $('hz-aba-direcao').getAttribute('aria-selected')};""")

        self.assertEqual(r, {"antes": ["hz-pane-ajustes"], "depois": ["hz-pane-direcao"], "marcada": "true"})

    def test_aba_ajustes_conta_os_knobs_da_variacao(self):
        r = self.sondar(pagina(*TRES), """const um = $('hz-conta-ajustes').textContent;
            activate(1); return [um, $('hz-conta-ajustes').textContent];""")

        self.assertEqual(r, ["1", ""])

    def test_selo_do_detector_abre_a_aba_do_detector(self):
        r = self.sondar(pagina(*TRES), "$('hz-detector-selo').click(); return !$('hz-pane-detector').hidden;")

        self.assertTrue(r)

    def test_no_comparar_o_painel_mostra_so_a_coluna_clicada(self):
        r = self.sondar(pagina(*TRES), """
            const antes = caption.textContent;
            variations[2].querySelector('p').dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
            return {antes, depois: caption.textContent,
                    foco: variations.map(v => v.hasAttribute('data-foco')),
                    botoes: document.querySelectorAll('#hz-escolha button').length,
                    knobs: document.querySelectorAll('#hz-knobs .hz-knob').length,
                    comparando: comparando()};""", "?comparar=1")

        self.assertIn("V1", r["antes"])
        self.assertIn("V3", r["depois"])
        self.assertEqual(r["foco"], [False, False, True])
        self.assertEqual(r["botoes"], 1)
        self.assertEqual(r["knobs"], 0, "V3 não tem knobs; os de V1 não podem continuar ali")
        self.assertTrue(r["comparando"])

    def test_fora_do_comparar_nenhuma_coluna_fica_em_foco(self):
        r = self.sondar(pagina(*TRES), "setComparar(false); return variations.some(v => v.hasAttribute('data-foco'));",
                        "?comparar=1")

        self.assertFalse(r)

    def test_largura_total_nao_tem_margem_nem_moldura(self):
        js = """const f = getComputedStyle(frame), w = getComputedStyle(stage.parentElement);
                return [f.borderTopWidth, f.borderTopLeftRadius, w.paddingLeft];"""

        self.assertEqual(self.sondar(pagina(*TRES), js, "?vw=full"), ["0px", "0px", "0px"])
        self.assertNotEqual(self.sondar(pagina(*TRES), js, "?vw=desktop"), ["0px", "0px", "0px"])

    def test_largura_livre_pela_url_e_desliga_ao_escolher_uma_fixa(self):
        r = self.sondar(pagina(*TRES), """
            const ligado = {w: Math.round(stage.getBoundingClientRect().width), medida: $('hz-medida').textContent,
                            sw: $('hz-livre').checked, url: location.search};
            setVw('mobile');
            return {ligado, depois: {sw: $('hz-livre').checked, estilo: stage.style.width, vw: stage.dataset.vw}};""",
            "?vw=livre&w=700")

        self.assertEqual(r["ligado"]["w"], 700)
        self.assertEqual(r["ligado"]["medida"], "700px")
        self.assertTrue(r["ligado"]["sw"])
        self.assertIn("w=700", r["ligado"]["url"])
        self.assertEqual(r["depois"], {"sw": False, "estilo": "", "vw": "mobile"})

    def test_largura_livre_tem_limite_minimo(self):
        r = self.sondar(pagina(*TRES), "return Math.round(stage.getBoundingClientRect().width);", "?vw=livre&w=10")

        self.assertEqual(r, 280)

    def test_atalhos_e_campo_de_texto_nao_dispara_atalho(self):
        r = self.sondar(pagina(*TRES), """
            const tecla = (k, alvo = document.body) => alvo.dispatchEvent(new KeyboardEvent('keydown', {key: k, bubbles: true}));
            tecla('ArrowRight'); const aba = ativa;
            tecla('t'); const tema = frame.dataset.theme;
            tecla('2'); const vw = stage.dataset.vw;
            tecla('t', $('hz-fonte-corpo')); const temaDepoisDoCampo = frame.dataset.theme;
            tecla('c'); const comp = comparando();
            return {aba, tema, vw, temaDepoisDoCampo, comp};""")

        self.assertEqual(r, {"aba": 1, "tema": "dark", "vw": "tablet", "temaDepoisDoCampo": "dark", "comp": True})

    def test_restaurar_volta_os_knobs_ao_padrao(self):
        r = self.sondar(pagina(*TRES), """
            aplicarKnob(variations[0], lerKnobs(variations[0]).lista[0], 0.9);
            $('hz-knobs-restaurar').click();
            return {valor: variations[0].style.getPropertyValue('--k-acento'),
                    faixa: document.querySelector('#hz-knobs input[type=range]').value};""")

        self.assertEqual(r, {"valor": "0.5", "faixa": "0.5"})

    def test_restaurar_some_quando_nao_ha_knobs(self):
        r = self.sondar(pagina(*TRES), "activate(1); return $('hz-knobs-restaurar').hidden;")

        self.assertTrue(r)

    def test_fonte_de_titulo_muda_so_os_titulos(self):
        r = self.sondar(pagina(*TRES), """
            await aplicarFonte('titulo', 'system-ui');
            const s = variations[0];
            return {h2: getComputedStyle(s.querySelector('h2')).fontFamily,
                    p: getComputedStyle(s.querySelector('p')).fontFamily, url: location.search};""")

        self.assertIn("system-ui", r["h2"])
        self.assertNotIn("system-ui", r["p"].split(",")[0])
        self.assertIn("font-titulo=system-ui", r["url"])

    def test_fonte_de_corpo_nao_muda_os_titulos(self):
        r = self.sondar(pagina(*TRES), """
            await aplicarFonte('corpo', 'system-ui');
            const s = variations[0];
            return {h2: getComputedStyle(s.querySelector('h2')).fontFamily,
                    p: getComputedStyle(s.querySelector('p')).fontFamily};""")

        self.assertTrue(r["p"].startswith("system-ui"))
        self.assertFalse(r["h2"].startswith("system-ui"))

    def test_nome_de_fonte_invalido_e_recusado_sem_carregar_nada(self):
        r = self.sondar(pagina(*TRES), """
            let pedidos = 0;
            linkGoogle = () => { pedidos++; return Promise.resolve(); };   // sem rede no teste
            await aplicarFonte('corpo', "Inter'); @import url(x");
            return {erro: $('hz-fonte-estado').hasAttribute('data-erro'), pedidos,
                    marcado: frame.hasAttribute('data-fonte-corpo')};""")

        self.assertEqual(r, {"erro": True, "pedidos": 0, "marcado": False})

    def test_nome_de_fonte_valido_pede_ao_google_fonts(self):
        r = self.sondar(pagina(*TRES), """
            const pedidos = [];
            linkGoogle = familia => { pedidos.push(familia); return Promise.resolve(); };
            await aplicarFonte('titulo', 'Bricolage Grotesque');
            return {pedidos, marcado: frame.getAttribute('data-fonte-titulo'), url: location.search};""")

        self.assertEqual(r["pedidos"], ["Bricolage+Grotesque:wght@400;500;600;700;800"])
        self.assertEqual(r["marcado"], "Bricolage Grotesque")
        self.assertIn("font-titulo=Bricolage+Grotesque", r["url"])

    def test_familia_sem_os_pesos_cai_no_pedido_so_com_o_nome(self):
        r = self.sondar(pagina(*TRES), """
            const pedidos = [];
            linkGoogle = familia => { pedidos.push(familia);
              return familia.includes(':') ? Promise.reject() : Promise.resolve(); };
            await aplicarFonte('corpo', 'Instrument Serif');
            return {pedidos, marcado: frame.getAttribute('data-fonte-corpo')};""")

        self.assertEqual(r["pedidos"], ["Instrument+Serif:wght@400;500;600;700;800", "Instrument+Serif"])
        self.assertEqual(r["marcado"], "Instrument Serif")

    def test_fonte_que_nao_existe_avisa_e_nao_aplica(self):
        r = self.sondar(pagina(*TRES), """
            linkGoogle = () => Promise.reject();
            await aplicarFonte('corpo', 'Fonte Inventada');
            return {erro: $('hz-fonte-estado').textContent, marcado: frame.hasAttribute('data-fonte-corpo')};""")

        self.assertIn("não existe no Google Fonts", r["erro"])
        self.assertFalse(r["marcado"])

    def test_direcao_le_a_paleta_renderizada(self):
        corpo = '<div class="bloco"><p>texto</p></div>'
        estilo = ".bloco { background: #123456; } .bloco p { color: #fedcba; }"
        r = self.sondar(pagina(secao(1, corpo, ativa=True), estilo=estilo),
                        "return Array.from(document.querySelectorAll('#hz-direcao .hz-cor')).map(c => c.title);")

        self.assertIn("#123456", r)
        self.assertIn("#fedcba", r)

    def test_direcao_inclui_o_fundo_do_canvas_quando_a_variacao_nao_tem_fundo(self):
        r = self.sondar(pagina(secao(1, "<p>x</p>", ativa=True)),
                        "return Array.from(document.querySelectorAll('#hz-direcao .hz-cor')).map(c => c.title);")

        self.assertIn("#f8fafc", r)

    def test_direcao_ignora_cor_transparente(self):
        estilo = ".bloco { background: rgb(1 2 3 / 0.1); }"
        r = self.sondar(pagina(secao(1, '<div class="bloco">x</div>', ativa=True), estilo=estilo),
                        "return Array.from(document.querySelectorAll('#hz-direcao .hz-cor')).map(c => c.title);")

        self.assertNotIn("#010203", r)

    def test_sem_servidor_comentar_e_escolher_ficam_desligados(self):
        r = self.sondar(pagina(*TRES), """return {comentar: $('hz-comentar').disabled,
            escolher: document.querySelector('#hz-escolha button').disabled};""")

        self.assertEqual(r, {"comentar": True, "escolher": True})


@unittest.skipUnless(CHROME, "sem Chrome na máquina")
class Conversa(unittest.TestCase):
    """Servido pelo serve.py: comentários, escolha e achado que aponta o elemento."""

    def setUp(self):
        # Sem o script do live-reload: a conexão dele nunca fecha e o tempo virtual do
        # Chrome headless não avançaria até a sonda.
        self._snippet, serve.RELOAD_SNIPPET = serve.RELOAD_SNIPPET, b""
        self.pasta = Path(tempfile.mkdtemp())
        self.servidor = serve.ThreadingServer(("127.0.0.1", 0), serve.make_handler(self.pasta))
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.servidor.server_address[1]}/"

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        serve.RELOAD_SNIPPET = self._snippet

    def sondar(self, html, corpo_js, consulta=""):
        (self.pasta / "index.html").write_text(com_sonda(html, corpo_js, espera=1200), encoding="utf-8")
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                            "--window-size=1400,900", "--virtual-time-budget=4000", "--dump-dom",
                            self.base + consulta], capture_output=True, text=True, timeout=60)
        return resposta(r.stdout)

    def test_comentario_feito_na_tela_chega_ao_arquivo_com_o_alvo_certo(self):
        corpo = '<div class="lista"><p>primeiro</p><p class="destaque">segundo</p></div>'
        r = self.sondar(pagina(secao(1, "<p>outra</p>", ativa=True), secao(2, corpo)), """
            activate(1);
            setComentando(true);
            variations[1].querySelector('.destaque').click();
            $('hz-balao-texto').value = 'Mais peso aqui';
            await salvarComentario();
            const lista = await api('/__comentarios');
            return {lista, achado: acharPorSeletor(variations[1], lista[0].seletor).textContent};""")

        gravado = json.loads((self.pasta / ".mockup" / "comentarios.json").read_text(encoding="utf-8"))
        self.assertEqual(gravado[0]["texto"], "Mais peso aqui")
        self.assertEqual(gravado[0]["variacao"], 2)
        self.assertEqual(gravado[0]["trecho"], "segundo")
        self.assertEqual(r["achado"], "segundo")

    def test_comentario_gravado_vira_pino_e_item_da_lista(self):
        (self.pasta / ".mockup").mkdir()
        (self.pasta / ".mockup" / "comentarios.json").write_text(json.dumps([
            {"id": 1, "variacao": 1, "titulo": "V1", "seletor": "h2", "trecho": "Título um", "texto": "maior"},
            {"id": 2, "variacao": 2, "titulo": "V2", "seletor": "h2", "trecho": "Título dois", "texto": "outro"}]),
            encoding="utf-8")

        r = self.sondar(pagina(*TRES), """return {
            pinos: document.querySelectorAll('.hz-pino').length,
            conta: $('hz-conta-comentarios').textContent,
            itens: Array.from(document.querySelectorAll('#hz-com-lista li')).map(li => li.textContent)};""")

        self.assertEqual(r["pinos"], 1, "só o comentário da variação visível tem pino")
        self.assertEqual(r["conta"], "2")
        self.assertEqual(len(r["itens"]), 2)
        self.assertIn("maior", r["itens"][0])

    def test_ligar_comentar_abre_a_aba_de_notas(self):
        r = self.sondar(pagina(*TRES), "setComentando(true); return !$('hz-pane-comentarios').hidden;")

        self.assertTrue(r)

    def test_seguir_com_esta_grava_a_escolha_com_os_knobs(self):
        self.sondar(pagina(*TRES), """
            aplicarKnob(variations[0], lerKnobs(variations[0]).lista[0], 0.7);
            await escolher(0);
            return true;""", "?vw=mobile")

        escolha = json.loads((self.pasta / ".mockup" / "escolha.json").read_text(encoding="utf-8"))
        self.assertEqual(escolha["variacao"], 1)
        self.assertEqual(escolha["titulo"], "V1")
        self.assertEqual(escolha["knobs"], {"acento": 0.7})
        self.assertEqual(escolha["vw"], "mobile")

    def test_achado_no_markup_aponta_o_elemento_da_linha(self):
        corpo = ('\n<div class="card">\n<p>Resumo do dia</p>\n'
                 '<button class="acao">Salvar — agora</button>\n</div>\n')
        r = self.sondar(pagina(secao(1, "<p>nada</p>", ativa=True), secao(2, corpo)), """
            const det = await api('/__detector');
            const a = det.achados.find(x => x.regra === 'travessao-na-interface');
            const alvo = localizarAchado(a);
            return {classe: alvo && alvo.className, variacao: alvo && variations.indexOf(alvo.closest('.variation'))};""")

        self.assertEqual(r, {"classe": "acao", "variacao": 1})

    def test_achado_no_css_aponta_o_elemento_do_seletor(self):
        corpo = '<div class="card">um</div><div class="caixa">dois</div>'
        estilo = "\n  .caixa {\n    box-shadow: 6px 6px 0 #222;\n  }"
        r = self.sondar(pagina(secao(1, corpo, ativa=True), estilo=estilo), """
            const det = await api('/__detector');
            const a = det.achados.find(x => x.regra === 'sombra-dura');
            const alvo = localizarAchado(a);
            return alvo && alvo.className;""")

        self.assertEqual(r, "caixa")

    def test_achado_que_aponta_fica_clicavel_na_lista(self):
        corpo = '<button>Salvar — agora</button>'
        r = self.sondar(pagina(secao(1, corpo, ativa=True)),
                        "return document.querySelectorAll('#hz-det-lista li[data-local]').length;")

        self.assertEqual(r, 1)


if __name__ == "__main__":
    unittest.main()
