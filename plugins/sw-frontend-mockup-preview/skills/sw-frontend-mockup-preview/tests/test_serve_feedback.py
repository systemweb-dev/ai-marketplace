"""O usuário fala com o agente pela própria tela: comenta um elemento e escolhe a vencedora.

O servidor grava isso em `<pasta>/.mockup/` (comentarios.json e escolha.json), que o agente
lê no turno seguinte. Três travas: gravar ali não dispara o live-reload (senão cada comentário
recarregaria a página no meio da digitação); só aceita JSON de verdade (um site qualquer aberto
no mesmo navegador não consegue mandar `application/json` para localhost sem preflight, e o
servidor não responde preflight); e o tamanho de tudo é limitado.
"""
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import serve  # noqa: E402

COMENTARIO = {"variacao": 2, "titulo": "Topologia: lista e resumo", "seletor": "div.painel > h2",
              "trecho": "Hoje", "texto": "Esse título pode ser maior", "vw": "desktop", "theme": "light"}


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        (self.pasta / "index.html").write_text("<p>oi</p>", encoding="utf-8")
        self.servidor = serve.ThreadingServer(("127.0.0.1", 0), serve.make_handler(self.pasta))
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.servidor.server_address[1]}"

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()

    def enviar(self, caminho, dados, tipo="application/json", origem=None):
        corpo = dados if isinstance(dados, bytes) else json.dumps(dados).encode("utf-8")
        pedido = urllib.request.Request(self.base + caminho, data=corpo, method="POST",
                                        headers={"Content-Type": tipo})
        if origem:
            pedido.add_header("Origin", origem)
        try:
            with urllib.request.urlopen(pedido, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as erro:
            return erro.code, json.loads(erro.read() or b"{}")

    def ler(self, caminho):
        with urllib.request.urlopen(self.base + caminho, timeout=5) as r:
            return json.loads(r.read())


class Comentarios(Base):
    def test_comentario_fica_gravado_para_o_agente_ler(self):
        status, criado = self.enviar("/__comentarios", COMENTARIO)

        gravado = json.loads((self.pasta / ".mockup" / "comentarios.json").read_text(encoding="utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(len(gravado), 1)
        self.assertEqual(gravado[0]["texto"], "Esse título pode ser maior")
        self.assertEqual(gravado[0]["seletor"], "div.painel > h2")
        self.assertEqual(gravado[0]["id"], criado["id"])
        self.assertIn("criado", gravado[0])

    def test_lista_e_apaga(self):
        _, um = self.enviar("/__comentarios", COMENTARIO)
        _, dois = self.enviar("/__comentarios", dict(COMENTARIO, texto="Outro ajuste"))

        self.enviar("/__comentarios/apagar", {"id": um["id"]})

        self.assertEqual([c["id"] for c in self.ler("/__comentarios")], [dois["id"]])

    def test_ids_nao_se_repetem_depois_de_apagar(self):
        _, um = self.enviar("/__comentarios", COMENTARIO)
        _, dois = self.enviar("/__comentarios", COMENTARIO)
        self.enviar("/__comentarios/apagar", {"id": dois["id"]})

        _, tres = self.enviar("/__comentarios", COMENTARIO)

        self.assertNotIn(tres["id"], (um["id"], dois["id"]))

    def test_sem_comentarios_devolve_lista_vazia(self):
        self.assertEqual(self.ler("/__comentarios"), [])

    def test_texto_vazio_e_recusado(self):
        status, resposta = self.enviar("/__comentarios", dict(COMENTARIO, texto="   "))

        self.assertEqual(status, 400)
        self.assertIn("erro", resposta)
        self.assertFalse((self.pasta / ".mockup" / "comentarios.json").exists())

    def test_texto_longo_demais_e_recusado(self):
        status, _ = self.enviar("/__comentarios", dict(COMENTARIO, texto="a" * 4001))

        self.assertEqual(status, 400)

    def test_campo_desconhecido_e_ignorado(self):
        self.enviar("/__comentarios", dict(COMENTARIO, caminho="/etc/passwd"))

        self.assertNotIn("caminho", self.ler("/__comentarios")[0])


class Escolha(Base):
    def test_escolha_grava_variacao_e_knobs(self):
        status, _ = self.enviar("/__escolha", {"variacao": 2, "titulo": "Topologia: lista e resumo",
                                               "knobs": {"lista": "compacta", "sombra": 0.6},
                                               "vw": "mobile", "theme": "dark"})

        gravado = json.loads((self.pasta / ".mockup" / "escolha.json").read_text(encoding="utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(gravado["variacao"], 2)
        self.assertEqual(gravado["knobs"], {"lista": "compacta", "sombra": 0.6})
        self.assertEqual(self.ler("/__escolha")["titulo"], "Topologia: lista e resumo")

    def test_nova_escolha_substitui_a_anterior(self):
        self.enviar("/__escolha", {"variacao": 1, "titulo": "A"})
        self.enviar("/__escolha", {"variacao": 3, "titulo": "C"})

        self.assertEqual(self.ler("/__escolha")["variacao"], 3)

    def test_variacao_precisa_ser_numero(self):
        status, _ = self.enviar("/__escolha", {"variacao": "2; rm", "titulo": "A"})

        self.assertEqual(status, 400)

    def test_booleano_nao_passa_por_numero(self):
        status, _ = self.enviar("/__escolha", {"variacao": True, "titulo": "A"})

        self.assertEqual(status, 400)

    def test_sem_escolha_devolve_nulo(self):
        self.assertIsNone(self.ler("/__escolha"))


class Travas(Base):
    def test_so_aceita_json(self):
        status, _ = self.enviar("/__comentarios", json.dumps(COMENTARIO).encode(), tipo="text/plain")

        self.assertEqual(status, 415)
        self.assertFalse((self.pasta / ".mockup").exists())

    def test_recusa_origem_de_outro_site(self):
        status, _ = self.enviar("/__comentarios", COMENTARIO, origem="https://exemplo.test")

        self.assertEqual(status, 403)

    def test_aceita_a_propria_origem(self):
        status, _ = self.enviar("/__comentarios", COMENTARIO, origem=self.base)

        self.assertEqual(status, 200)

    def test_corpo_grande_demais_e_recusado(self):
        status, _ = self.enviar("/__comentarios", b"{" + b" " * 70000 + b"}")

        self.assertEqual(status, 413)

    def test_json_quebrado_e_recusado(self):
        status, _ = self.enviar("/__comentarios", b"{nao e json")

        self.assertEqual(status, 400)

    def test_rota_desconhecida_de_post_da_404(self):
        status, _ = self.enviar("/index.html", {"x": 1})

        self.assertEqual(status, 404)

    def test_gravar_feedback_nao_dispara_o_live_reload(self):
        antes = serve.snapshot(self.pasta)

        self.enviar("/__comentarios", COMENTARIO)
        self.enviar("/__escolha", {"variacao": 1, "titulo": "A"})

        self.assertEqual(serve.snapshot(self.pasta), antes)

    def test_editar_o_index_continua_disparando(self):
        antes = serve.snapshot(self.pasta)

        (self.pasta / "index.html").write_text("<p>mudou</p>", encoding="utf-8")
        (self.pasta / "outro.css").write_text("p{}", encoding="utf-8")

        self.assertNotEqual(serve.snapshot(self.pasta), antes)


if __name__ == "__main__":
    unittest.main()
